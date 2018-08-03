#!/usr/bin/env python
from __future__ import print_function
import argparse
import logging
import os
import tempfile
import yaml

from collections import defaultdict
from datetime import datetime
from subprocess import call, Popen, PIPE

from insights import dr, get_filters
from insights.core import blacklist
from insights.core.serde import marshal, ser
from insights.core.spec_factory import FileProvider
from insights.util import fs

SAFE_ENV = {
    "PATH": os.path.pathsep.join(["/bin", "/usr/bin", "/sbin", "/usr/sbin"])
}

log = logging.getLogger(__name__)

default_manifest = '''
---
version: 0
context:
    class: insights.core.context.HostContext
    args:
        timeout: 10 # timeout in seconds for commands. Doesn't apply to files.

default_component_enabled: false
blacklist:
    commands: []
    files: []
packages:
    - insights.specs.default
persist:
    - name: insights.specs.Specs
      enabled: true
max_serializable_file_size: 524288
configs:
    - name: insights.specs.Specs
      enabled: true
    - name: insights.specs.default.DefaultSpecs
      enabled: true
    - name: insights.core.spec_factory
      enabled: true
'''.strip()


def check_output(cmd, env=SAFE_ENV):
    proc = Popen(cmd, stdout=PIPE, env=env)
    output, error = proc.communicate()
    if error:
        log.warning(error)
    return output.decode("utf-8")


def copy(src, dst, filters=None, bufsize=-1):
    fs.ensure_path(os.path.dirname(dst), mode=0o770)

    if filters:
        filters = "\n".join(filters)
        args = ["grep", "-F", filters, src]
        with open(dst, "wb") as out:
            Popen(args, bufsize=bufsize, stdout=out).wait()
    else:
        call(["cp", src, dst], env=SAFE_ENV)


def load_manifest(data):
    if isinstance(data, dict):
        return data
    doc = yaml.safe_load(data)
    if not isinstance(doc, dict):
        raise Exception("Manifest didn't result in dict.")
    return doc


def apply_default_enabled(default_enabled):
    for k in dr.ENABLED:
        dr.ENABLED[k] = default_enabled

    enabled = defaultdict(lambda: default_enabled)
    enabled.update(dr.ENABLED)
    dr.ENABLED = enabled


def load_packages(pkgs):
    for p in pkgs:
        dr.load_components(p, continue_on_error=False)


def apply_blacklist(cfg):
    for b in cfg.get("commands", []):
        blacklist.add_command(b)

    for b in cfg.get("files", []):
        blacklist.add_file(b)


def apply_configs(configs):
    delegate_keys = sorted(dr.DELEGATES, key=dr.get_name)
    for comp_cfg in configs:
        name = comp_cfg["name"]
        for c in delegate_keys:
            delegate = dr.DELEGATES[c]
            cname = dr.get_name(c)
            if cname.startswith(name):
                dr.ENABLED[c] = comp_cfg.get("enabled", True)
                delegate.metadata.update(comp_cfg.get("metadata", {}))
                if hasattr(c, "timeout"):
                    c.timeout = comp_cfg.get("timeout")
            if cname == name:
                break


def create_context(ctx):
    ctx_cls_name = ctx.get("class", "insights.core.context.HostContext")
    if "." not in ctx_cls_name:
        ctx_cls_name = "insights.core.context." + ctx_cls_name
    ctx_cls = dr.get_component(ctx_cls_name)
    ctx_args = ctx.get("args", {})
    return ctx_cls(**ctx_args)


def relocate(results, root, max_size, filters):
    def move_it(result):
        if not isinstance(result, FileProvider):
            return result

        if not result.loaded:
            src = result.path
            if max_size and os.path.getsize(src) > max_size:
                rel = result.relative_path
                dst = os.path.join(root, rel)
                copy(src, dst, filters=filters)
            else:
                result.content
        return result

    if isinstance(results, list):
        return [move_it(r) for r in results]
    else:
        return move_it(results)


def make_persister(to_persist, root, max_size=0):
    ser_name = dr.get_base_module_name(ser)

    raw_data_dir = os.path.join(root, "raw_data")
    fs.ensure_path(raw_data_dir, mode=0o770)

    data_dir = os.path.join(root, "data")
    fs.ensure_path(data_dir, mode=0o770)

    def persister(c, broker):
        name = dr.get_name(c)
        if c in broker and c in to_persist:
            value = broker.get(c)
            if value:
                value = relocate(value, raw_data_dir, max_size, get_filters(c))

            doc = {
                "name": name,
                "time": broker.exec_times.get(c),
                "results": marshal(value),
                "errors": marshal(broker.exceptions.get(c))
            }

            path = os.path.join(data_dir, name + "." + ser_name)
            try:
                with open(path, "w") as f:
                    ser.dump(doc, f)
            except Exception as boom:
                log.error("Could not serialize %s to %s: %s" % (name, ser_name, boom))
                fs.remove(path)

    return persister


def get_to_persist(persisters):
    def specs():
        for p in persisters:
            if isinstance(p, dict):
                yield p["name"], p.get("enabled", True)
            else:
                yield p, True

    components = sorted(dr.DELEGATES, key=dr.get_name)
    names = dict((c, dr.get_name(c)) for c in components)

    results = set()
    for p, e in specs():
        for c in components:
            if names[c].startswith(p):
                if e:
                    results.add(c)
                elif c in results:
                    results.remove(c)
    return results


def create_archive(path):
    root_path = os.path.dirname(path)
    relative_path = os.path.basename(path)
    archive_path = path + ".tar.gz"

    cmd = ["tar", "-C", root_path, "-czf", archive_path, relative_path]
    call(cmd, env=SAFE_ENV)
    fs.remove(path)
    return archive_path


def collect(manifest=default_manifest, tmp_path=None, compress=False):
    manifest = load_manifest(manifest)
    tmp_path = tmp_path or tempfile.gettempdir()

    apply_default_enabled(manifest.get("default_component_enabled", False))
    load_packages(manifest.get("packages", []))
    apply_blacklist(manifest.get("blacklist", {}))
    apply_configs(manifest.get("configs", []))

    ctx = create_context(manifest.get("context", {}))
    to_persist = get_to_persist(manifest.get("persist", []))
    max_file_size = manifest.get("max_serializable_file_size", 0)

    hostname = check_output(["hostname", "-f"]).strip()
    suffix = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    relative_path = "insights-%s-%s" % (hostname, suffix)
    output_path = os.path.join(tmp_path, relative_path)
    fs.ensure_path(output_path)
    fs.touch(os.path.join(output_path, "insights_archive.txt"))

    broker = dr.Broker()
    broker[ctx.__class__] = ctx
    broker.add_observer(make_persister(to_persist, output_path, max_file_size))
    list(dr.run_incremental(broker=broker))

    if compress:
        return create_archive(output_path)
    return output_path


def main():
    p = argparse.ArgumentParser()
    p.add_argument("-m", "--manifest", help="Manifest yaml.")
    p.add_argument("-o", "--out_path", help="Path to write output data.")
    p.add_argument("-q", "--quiet", help="Error output only.", action="store_true")
    p.add_argument("-v", "--verbose", help="Verbose output.", action="store_true")
    p.add_argument("--debug", help="Debug output.", action="store_true")
    args = p.parse_args()

    level = logging.WARNING
    if args.verbose:
        level = logging.INFO
    if args.debug:
        level = logging.DEBUG
    if args.quiet:
        level = logging.ERROR

    logging.basicConfig(level=level)

    if args.manifest:
        with open(args.manifest) as f:
            manifest = f.read()
    else:
        manifest = default_manifest

    out_path = args.out_path or tempfile.gettempdir()
    archive = collect(manifest, out_path, compress=True)
    print("Archive: %s" % archive)


if __name__ == "__main__":
    main()

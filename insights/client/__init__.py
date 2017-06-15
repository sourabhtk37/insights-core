class InsightsClient(object):

    def __init__(self, options=None):
        """
            Parameters:
                options (object): Output of argparse
        """
        self.options = options

    def fetch(self):
        """
            returns (str): path to new egg.  None if no update.
        """
        pass

    def collect(self, format="json", options=None):
        pass

    def upload(self):
        pass

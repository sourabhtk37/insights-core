"""
NovaApiLog - file ``/var/log/nova/nova-api.log``
================================================
"""
from .. import LogFileOutput, parser


@parser('nova-api_log')
class NovaApiLog(LogFileOutput):
    """Class for parsing the ``/var/log/nova/nova-api.log`` file.

    Note:
        Please refer to its super-class ``LogFileOutput``
    """
    def get(self, keywords):
        """
        Returns all lines that contain all keywords.

        Parameters:
            keywords(str or list): one or more strings to find in the lines.

        Returns:
            (list): The list of lines that contain all the keywords given.
        """
        r = []
        for l in self.lines:
            if type(keywords) == list and all([word in l for word in keywords]):
                r.append(l)
            elif type(keywords) == str and keywords in l:
                r.append(l)
        return r

    def get_after(self, timestamp, lines=None):
        """
        Get a list of lines after the given time stamp.

        Parameters:
            timestamp(datetime.datetime): log lines after this time are
                returned.
            lines(list): the list of log lines to search (e.g. from a get).
                If not supplied, all available lines are searched.

        Yields:
            Log lines with time stamps after the given date and time, in the
            same format they were supplied.
        """
        return super(NovaApiLog, self).get_after(timestamp, lines, '%Y-%m-%d %H:%M:%S')

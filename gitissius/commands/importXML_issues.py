import gitissius.commands as commands
from gitissius.database import Issue, Comment
import gitissius.common as common
from xml.etree import ElementTree as et
import dateutil.parser
import dateutil.tz
import datetime
import logging

# BE: ("target", "wishlist", "minor", "serious", "critical",
#      "fatal")
# GI: ('high', 'medium', 'low')
SEVERITY_MAP = {
    'target': 'low',
    'wishlist': 'low',
    'minor': 'low',
    'serious': 'medium',
    'critical': 'high',
    'fatal': 'high'
}

# BE: ("unconfirmed", "open", "assigned", "test", "closed",
# "fixed", "wontfix")
# GI: ('new', 'assigned', 'invalid', 'closed")
STATUS_MAP = {
    'unconfirmed': 'new',
    'open': 'new',
    'assigned': 'assigned',
    'test': 'assigned',
    'closed': 'closed',
    'fixed': 'closed',
    'wontfix': 'invalid'
}


class Command(commands.GitissiusCommand):
    """
    Import issues from BugsEverywhere XML
    """
    name = "importXML"
    aliases = []
    help = "Import Issues from XML"

    def __init__(self):
        super(Command, self).__init__()

    def __map_property(self, prop, last_update=None):
        PROP_MAP = {
            "short-name": None,  # git ID
            "summary": 'title',
            "severity": 'severity',
            "status": 'status',
            "reporter": 'reported_from',
            "creator": None,  # doesn't seem to exist
            # <created>Mon, 12 Aug 2013 11:01:54 +0000</created>
            "created": 'created_on'
        }

        logging.debug("%s\nprop = %s",
                      '=' * 30, et.tostring(prop))

        key = None
        if prop.tag in PROP_MAP:
            key = PROP_MAP[prop.tag]

        if key is None:
            return None

        if key == 'severity':
            value = SEVERITY_MAP[prop.text]
        elif key == 'status':
            value = STATUS_MAP[prop.text]
        elif key == 'created_on':
            value = dateutil.parser.parse(prop.text) \
                if prop.text is not None else \
                datetime.datetime(1970, 1, 1,
                                  0, 0, 0, 0, dateutil.tz.tzutc())
        else:
            value = prop.text if prop.text is not None else ''

        return key, value

    @staticmethod
    def __parse_comment(inElem):
        out = {}
        PROP_MAP = {
            "author": "reported_from",
            "date": 'created_on',
            "body": 'description'
        }

        for child in inElem.findall("*"):
            if child.tag in PROP_MAP:
                key = PROP_MAP[child.tag]
            else:
                key = None

            if key == 'created_on':
                value = dateutil.parser.parse(child.text) \
                    if child.text is not None else \
                    datetime.datetime(1970, 1, 1,
                                      0, 0, 0, 0, dateutil.tz.tzutc())
            else:
                value = child.text if child.text is not None else ''

            if key is not None:
                out[key] = value

        return out

    def __parse_bug(self, inElem):
        out = {}

        for prop in inElem.findall('*'):
            value = self.__map_property(prop)
            if value is not None and value[0] is not None:
                out[value[0]] = value[1]

        out['updated_on'] = out.get('created_on')

        logging.debug("out = %s", out)
        return out

    def _execute(self, options, args):
        in_file_name = args[0]

        issue_XML = et.iterparse(in_file_name)

        for event, elem in issue_XML:
            if elem.tag == "bug":
                logging.debug("elem = %s", et.tostring(elem))
                issue = Issue.load(self.__parse_bug(elem))
                for child in elem.findall("comment"):
                    comment = self.__parse_comment(child)
                    issue_time = issue.get_property('updated_on')
                    try:
                        issue_time.set_value(max(comment['created_on'],
                                             issue_time.value))
                    except ValueError:
                        logging.debug("comment['created_on'] = %s",
                                      comment['created_on'])
                        logging.debug("issue_time.value = %s",
                                      issue_time.value)
                        raise
                    issue._comments.append(
                        Comment.load(comment))

                # add to repo
                common.git_repo[issue.path] = issue.serialize(indent=4)

                # commit
                common.git_repo.commit("Added issue %s" %
                                       issue.get_property('id'))

        print "File imported."

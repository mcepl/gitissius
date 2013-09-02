import gitissius.commands as commands
from gitissius.database import Issue, Comment
import gitissius.common as common
from xml.etree import ElementTree as et
import dateutil.parser
import logging


class Command(commands.GitissiusCommand):
    """
    Import issues from BugsEverywhere XML
    """
    name = "importXML"
    aliases = []
    help = "Import Issues from XML"

    def __init__(self):
        super(Command, self).__init__()

    def __map_property(self, prop):
        if prop.tag == "short-name":
            return None, None  # git ID

        elif prop.tag == "summary":
            return 'title', prop.text

        elif prop.tag == "severity":
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
            return 'severity', SEVERITY_MAP[prop.text]

        elif prop.tag == "status":
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
            return 'status', STATUS_MAP[prop.text]

        elif prop.tag == "reporter":
            return 'reported_from', prop.text

        elif prop.tag == "creator":
            return None, None  # doesn't seem to exist

        elif prop.tag == "created":
            # <created>Mon, 12 Aug 2013 11:01:54 +0000</created>
            return 'created_on', dateutil.parser.parse(prop.text)

    def __parse_comment(self, inElem):
        out = {}
        for child in inElem.findall("*"):
            if child.tag == 'author':
                out['reported_from'] = child.text
            elif child.tag == 'date':
                out['created_on'] = dateutil.parser.parse(child.text)
            elif child.tag == 'body':
                out['description'] = child.text

        return out

    def __parse_bug(self, inElem):
        out = {  # some default values
            'type': 'bug'
        }

        for prop in inElem.findall('*'):
                value = self.__map_property(prop)
                if value is not None and value[0] is not None:
                    out[value[0]] = value[1]

        logging.debug("out = %s", out)
        return out

    def _execute(self, options, args):
        """
        self._print_order = ['id', 'title', 'type', 'severity',
                             'reported_from', 'assigned_to', 'created_on',
                             'updated_on', 'status', 'description' ]
        """
        # from gitissius.database import Issue
        #in_file_name = args[0]
        in_file_name = "/home/matej/archiv/2012/projekty/" + \
            "github-issues-export/issues.xml"

        issue_XML = et.iterparse(in_file_name)

        for event, elem in issue_XML:
            if elem.tag == "bug":
                logging.debug("elem = %s", et.tostring(elem))
                issue = Issue.load(self.__parse_bug(elem))
                for child in elem.findall("comment"):
                    issue._comments.append(
                        Comment.load(self.__parse_comment(child)))

                # add to repo
                common.git_repo[issue.path] = issue.serialize(indent=4)

                # commit
                common.git_repo.commit("Added issue %s" %
                                       issue.get_property('id'))

        print "File imported."

from django.urls import reverse
from .dojo_test_case import DojoTestCase
from dojo.models import JIRA_Issue
import json

# from unittest import skip
import logging
import dojo.jira_link.helper as jira_helper

logger = logging.getLogger(__name__)


class JIRAWebhookTest(DojoTestCase):
    fixtures = ["dojo_testdata.json"]

    jira_issue_comment_template_json = {
        "timestamp": 1605117321425,
        "webhookEvent": "comment_created",
        "comment": {
            "self": "http://www.testjira.com/rest/api/2/issue/2/comment/456843",
            "id": "456843",
            "author": {
                "self": "http://www.testjira.com/rest/api/2/user?username=valentijn",
                "name": "valentijn",
                "avatarUrls": {
                    "48x48": "http://www.testjira.com/secure/useravatar?ownerId=valentijn&avatarId=11101",
                    "24x24": "http://www.testjira.com/secure/useravatar?size=small&ownerId=valentijn&avatarId=11101",
                    "16x16": "http://www.testjira.com/secure/useravatar?size=x small&ownerId=valentijn&avatarId=11101",
                    "32x32": "http://www.testjira.com/secure/useravatar?size=medium&ownerId=valentijn&avatarId=11101",
                },
                "displayName": "Valentijn Scholten",
                "active": "true",
                "timeZone": "Europe/Amsterdam",
            },
            "body": "test2",
            "updateAuthor": {
                "self": "http://www.testjira.com/rest/api/2/user?username=valentijn",
                "name": "valentijn",
                "avatarUrls": {
                    "48x48": "http://www.testjira.com/secure/useravatar?ownerId=valentijn&avatarId=11101",
                    "24x24": "http://www.testjira.com/secure/useravatar?size=small&ownerId=valentijn&avatarId=11101",
                    "16x16": "http://www.testjira.com/secure/useravatar?size=xsmall&ownerId=valentijn&avatarId=11101",
                    "32x32": "http://www.testjira.com/secure/useravatar?size=medium&ownerId=valentijn&avatarId=11101",
                },
                "displayName": "Valentijn Scholten",
                "active": "true",
                "timeZone": "Europe/Amsterdam",
            },
            "created": "2020-11-11T18:55:21.425+0100",
            "updated": "2020-11-11T18:55:21.425+0100",
        },
    }

    jira_issue_comment_template_json_with_email = {
        "timestamp": 1605117321425,
        "webhookEvent": "comment_created",
        "comment": {
            "self": "http://www.testjira.com/rest/api/2/issue/2/comment/456843",
            "id": "456843",
            "author": {
                "self": "http://www.testjira.com/rest/api/2/user?username=valentijn",
                "emailAddress": "darthvaalor@testme.nl",
                "avatarUrls": {
                    "48x48": "http://www.testjira.com/secure/useravatar?ownerId=valentijn&avatarId=11101",
                    "24x24": "http://www.testjira.com/secure/useravatar?size=small&ownerId=valentijn&avatarId=11101",
                    "16x16": "http://www.testjira.com/secure/useravatar?size=x small&ownerId=valentijn&avatarId=11101",
                    "32x32": "http://www.testjira.com/secure/useravatar?size=medium&ownerId=valentijn&avatarId=11101",
                },
                "displayName": "Valentijn Scholten",
                "active": "true",
                "timeZone": "Europe/Amsterdam",
            },
            "body": "test2",
            "updateAuthor": {
                "self": "http://www.testjira.com/rest/api/2/user?username=valentijn",
                "emailAddress": "darthvaalor@testme.nl",
                "avatarUrls": {
                    "48x48": "http://www.testjira.com/secure/useravatar?ownerId=valentijn&avatarId=11101",
                    "24x24": "http://www.testjira.com/secure/useravatar?size=small&ownerId=valentijn&avatarId=11101",
                    "16x16": "http://www.testjira.com/secure/useravatar?size=xsmall&ownerId=valentijn&avatarId=11101",
                    "32x32": "http://www.testjira.com/secure/useravatar?size=medium&ownerId=valentijn&avatarId=11101",
                },
                "displayName": "Valentijn Scholten",
                "active": "true",
                "timeZone": "Europe/Amsterdam",
            },
            "created": "2020-11-11T18:55:21.425+0100",
            "updated": "2020-11-11T18:55:21.425+0100",
        },
    }

    jira_issue_update_template_string = """
{
   "timestamp":1605117321475,
   "webhookEvent":"jira:issue_updated",
   "issue_event_type_name":"issue_commented",
   "user":{
      "self":"https://jira.onpremise.org/rest/api/2/user?username=valentijn",
      "name":"valentijn",
      "emailAddress ":"valentijn.scholten@isaac.nl",
      "avatarUrls":{
         "48x48":"https://jira.onpremise.org/secure/useravatar?ownerId=valentijn&avatarId=11101",
         "24x24":"http s://jira.onpremise.org/secure/useravatar?size=small&ownerId=valentijn&avatarId=11101",
         "16x16":"https://jira.onpremise.org/secure/useravatar?size=xsmall& ownerId=valentijn&avatarId=11101",
         "32x32":"https://jira.onpremise.org/secure/useravatar?size=medium&ownerId=valentijn&avatarId=11101"
      },
      "displayName ":"Valentijn Scholten",
      "active":"true",
      "timeZone":"Europe/Amsterdam"
   },
   "issue":{
      "id":"2",
      "self":"https://jira.onpremise.org/rest/api/2/issue/2 ",
      "key":"ISEC-277",
      "fields":{
         "issuetype":{
            "self":"https://jira.onpremise.org/rest/api/2/issuetype/3",
            "id":"3",
            "description":"A task is some piece o f work that can be assigned to a user. This does not always result in a quotation/estimate, as it is often some task that needs to be performe d in the context of an existing contract. ",
            "iconUrl":"https://jira.onpremise.org/secure/viewavatar?size=xsmall&avatarId=16681&avatarType=issuetype",
            "name":"Task",
            "subtask":false,
            "avatarId":16681
         },
         "project":{
            "self":"https://jira.onpremise.org/rest/api/2/project/13532",
            "id":"13532",
            "key":"ISEC",
            "name":"ISAAC security",
            "projectTypeKey":"software",
            "avatarUrls":{
               "48x48":"https://jira.onpremise.org/secure/projectavatar?avatarId=14803",
               "24x24":"https://jira.onpremise.org/secure/projectavatar?size=small&avatarId=14803",
               "16x16":"https://jira.onpremise.org/secure/projectavatar?size=xsmall&avatarId=14803",
               "32x32":"https://jira.onpremise.org/secure/projectavatar?size=medium&avatarId=14803"
            },
            "projectCategory":{
               "self":"https://jira.onpremise.org/rest/api/2/projectCategory/10032",
               "id":"10032",
               "description":"All internal isaac projects.",
               "name":"isaac internal"
            }
         },
         "fixVersions":[
         ],
         "customfield_11440":"0|y02wb8: ",
                        "resolution":{
                            "self":"http://www.testjira.com/rest/api/2/resolution/11",
                            "id":"11",
                            "description":"Cancelled by the customer.",
                            "name":"Cancelled"
                        },
         "resolutiondate":null,
         "workratio":"-1",
         "lastViewed":"2020-11-11T18:54:32.489+0100",
         "watches":{
            "self":"https://jira.onpremise.org/rest/api/2/issue/ISEC-277/watchers",
            "watchCount":1,
            "isWatching":"true"
         },
         "customfield_10060":[
            "dojo_user(dojo_user)",
            "valentijn(valentijn)"
         ],
         "customfield_10182":null,
         "created":"2019-04-04T15:38:21.248+0200",
         "customfield_12043":null,
         "customfield_10340":null,
         "customfield_10341":null,
         "customfield_12045":null,
         "customfield_10100":null,
         "priority":{
            "self":"https://jira.onpremise.org/rest/api/2/priority/5",
            "iconUrl":"https://jira.onpremise.org/images/icons/priorities/trivial.svg",
            "name":"Trivial (Sev5)",
            "id":"5"
         },
         "customfield_10740":null,
         "labels":[
            "NPM_Test",
            "defect-dojo",
            "security"
         ],
         "timeestimate":null,
         "aggregatetimeoriginalestimate":null,
         "issuelinks":[
         ],
         "assignee":{
            "self":"https://jira.onpremise.org/rest/api/2/user?username=valentijn",
            "name":"valentijn",
            "emailAddress":"valentijn.scholten@isaac.nl",
            "avatarUrls":{
               "48x48":"https://jira.onpremise.org/secure/useravatar?ownerId=valentijn&avatarId=11101",
               "24x24":"https://jira.onpremise.org/secure/useravatar?size=small&ownerId=valentijn&avatarId=11101",
               "16x16":"https://jira.onpremise.org/secure/useravatar?size=xsmall&ownerId=valentijn&avatarId=11101",
               "32x32":"https://jira.onpremise.org/secure/useravatar?size=medium&ownerId=valentijn&avatarId=11101"
            },
            "displayName":"Valentijn Scholten",
            "active":"true",
            "timeZone":"Europe/Amsterdam"
         },
         "updated":"2020-11-11T18:54:32.155+0100",
         "status":{
            "self":"https://jira.onpremise.org/rest/api/2/status/10022",
            "description":"Incoming/New issues.",
            "iconUrl":"https://jira.onpremise.org/isaac_content/icons/isaac_status_new.gif",
            "name":"Closed",
            "id":"10022",
            "statusCategory":{
               "self":"https://jira.onpremise.org/rest/api/2/statuscategory/2",
               "id":2,
               "key":"new",
               "colorName":"blue-gray",
               "name":"To Do"
            }
         },
         "components":[
         ],
         "customfield_10051":"2020-11-11T18:54:32.155+0100",
         "timeoriginalestimate":null,
         "customfield_10052":null,
         "description":"description",
         "customfield_10010":null,
         "timetracking":{
         },
         "attachment":[
         ],
         "aggregatetimeestimate":null,
         "summary":"Regular Expression Denial of Service - (braces, <2.3.1)",
         "creator":{
            "self":"https://jira.onpremise.org/rest/api/2/user?username=dojo_user",
            "name":"dojo_user",
            "key":"dojo_user",
            "emailAddress":"defectdojo@isaac.nl",
            "avatarUrls":{
               "48x48":"https://www.gravatar.com/avatar/9637bfb970eff6176357df615f548f1c?d=mm&s=48",
               "24x24":"https://www.gravatar.com/avatar/9637bfb970eff6176357df615f548f1c?d=mm&s=24",
               "16x16":"https://www.gravatar.com/avatar/9637bfb970eff6176357df615f548f1c?d=mm&s=16",
               "32x32":"https://www.gravatar.com/avatar/9637bfb970eff6176357df615f548f1c?d=mm&s=32"
            },
            "displayName":"Defect Dojo",
            "active":"true",
            "timeZone":"Europe/Amsterdam"
         },
         "subtasks":[
         ],
         "customfield_10240":"9223372036854775807",
         "reporter":{
            "self":"https://jira.onpremise.org/rest/api/2/user?username=dojo_user",
            "name":"dojo_user",
            "key":"dojo_user",
            "emailAddress":"defectdojo@isaac.nl",
            "avatarUrls":{
               "48x48":"https://www.gravatar.com/avatar/9637bfb970eff6176357df615f548f1c?d=mm&s=48",
               "24x24":"https://www.gravatar.com/avatar/9637bfb970eff6176357df615f548f1c?d=mm&s=24",
               "16x16":"https://www.gravatar.com/avatar/9637bfb970eff6176357df615f548f1c?d=mm&s=16",
               "32x32":"https://www.gravatar.com/avatar/9637bfb970eff6176357df615f548f1c?d=mm&s=32"
            },
            "displayName":"Defect Dojo",
            "active":"true",
            "timeZone":"Europe/Amsterdam"
         },
         "aggregateprogress":{
            "progress":0,
            "total":0
         },
         "customfield_10640":"9223372036854775807",
         "customfield_10641":null,
         "environment":null,
         "duedate":null,
         "progress":{
            "progress":0,
            "total":0
         },
         "comment":{
            "comments":[
               {
                  "self":"https://jira.onpremise.org/rest/api/2/issue/2/comment/456841",
                  "id":"456841",
                  "author":{
                     "self":"https://jira.onpremise.org/rest/api/2/user?username=valentijn",
                     "name":"valentijn",
                     "emailAddress":"valentijn.scholten@isaac.nl",
                     "avatarUrls":{
                        "48x48":"https://jira.onpremise.org/secure/useravatar?ownerId=valentijn&avatarId=11101",
                        "24x24":"https://jira.onpremise.org/secure/useravatar?size=small&ownerId=valentijn&avatarId=11101",
                        "16x16":"https://jira.onpremise.org/secure/useravatar?size=xsmall&ownerId=valentijn&avatarId=11101",
                        "32x32":"https://jira.onpremise.org/secure/useravatar?size=medium&ownerId=valentijn&avatarId=11101"
                     },
                     "displayName":"Valentijn Scholten",
                     "active":"true",
                     "timeZone":"Europe/Amsterdam"
                  },
                  "body":"test comment valentijn",
                  "updateAuthor":{
                     "self":"https://jira.onpremise.org/rest/api/2/user?username=valentijn",
                     "name":"valentijn",
                     "emailAddress":"valentijn.scholten@isaac.nl",
                     "avatarUrls":{
                        "48x48":"https://jira.onpremise.org/secure/useravatar?ownerId=valentijn&avatarId=11101",
                        "24x24":"https://jira.onpremise.org/secure/useravatar?size=small&ownerId=valentijn&avatarId=11101",
                        "16x16":"https://jira.onpremise.org/secure/useravatar?size=xsmall&ownerId=valentijn&avatarId=11101",
                        "32x32":"https://jira.onpremise.org/secure/useravatar?size=medium&ownerId=valentijn&avatarId=11101"
                     },
                     "displayName":"Valentijn Scholten",
                     "active":"true",
                     "timeZone":"Europe/Amsterdam"
                  },
                  "created":"2020-11-11T18:54:32.155+0100",
                  "updated":"2020-11-11T18:54:32.155+0100"
               },
               {
                  "self":"https://jira.onpremise.org/rest/api/2/issue/2/comment/456843",
                  "id":"456843",
                  "author":{
                     "self":"https://jira.onpremise.org/rest/api/2/user?username=valentijn",
                     "name":"valentijn",
                     "emailAddress":"valentijn.scholten@isaac.nl",
                     "avatarUrls":{
                        "48x48":"https://jira.onpremise.org/secure/useravatar?ownerId=valentijn&avatarId=11101",
                        "24x24":"https://jira.onpremise.org/secure/useravatar?size=small&ownerId=valentijn&avatarId=11101",
                        "16x16":"https://jira.onpremise.org/secure/useravatar?size=xsmall&ownerId=valentijn&avatarId=11101",
                        "32x32":"https://jira.onpremise.org/secure/useravatar?size=medium&ownerId=valentijn&avatarId=11101"
                     },
                     "displayName":"Valentijn Scholten",
                     "active":"true",
                     "timeZone":"Europe/Amsterdam"
                  },
                  "body":"test2",
                  "updateAuthor":{
                     "self":"https://jira.onpremise.org/rest/api/2/user?username=valentijn",
                     "name":"valentijn",
                     "emailAddress":"valentijn.scholten@isaac.nl",
                     "avatarUrls":{
                        "48x48":"https://jira.onpremise.org/secure/useravatar?ownerId=valentijn&avatarId=11101",
                        "24x24":"https://jira.onpremise.org/secure/useravatar?size=small&ownerId=valentijn&avatarId=11101",
                        "16x16":"https://jira.onpremise.org/secure/useravatar?size=xsmall&ownerId=valentijn&avatarId=11101",
                        "32x32":"https://jira.onpremise.org/secure/useravatar?size=medium&ownerId=valentijn&avatarId=11101"
                     },
                     "displayName":"Valentijn Scholten",
                     "active":"true",
                     "timeZone":"Europe/Amsterdam"
                  },
                  "created":"2020-11-11T18:55:21.425+0100",
                  "updated":"2020-11-11T18:55:21.425+0100"
               }
            ],
            "maxResults":2,
            "total":2,
            "startAt":0
         },
         "worklog":{
            "startAt":0,
            "maxResults":20,
            "total":0,
            "worklogs":[
            ]
         }
      }
   },
   "comment":{
      "self":"https://jira.onpremise.org/rest/api/2/issue/2/comment/456843",
      "id":"456843",
      "author":{
         "self":"https://jira.onpremise.org/rest/api/2/user?username=valentijn",
         "name":"valentijn",
         "emailAddress":"valentijn.scholten@isaac.nl",
         "avatarUrls":{
            "48x48":"https://jira.onpremise.org/secure/useravatar?ownerId=valentijn&avatarId=11101",
            "24x24":"https://jira.onpremise.org/secure/useravatar?size=small&ownerId=valentijn&avatarId=11101",
            "16x16":"https://jira.onpremise.org/secure/useravatar?size=xsmall&ownerId=valentijn&avatarId=11101",
            "32x32":"https://jira.onpremise.org/secure/useravatar?size=medium&ownerId=valentijn&avatarId=11101"
         },
         "displayName":"Valentijn Scholten",
         "active":"true",
         "timeZone":"Europe/Amsterdam"
      },
      "body":"test2",
      "updateAuthor":{
         "self":"https://jira.onpremise.org/rest/api/2/user?username=valentijn",
         "name":"valentijn",
         "emailAddress":"valentijn.scholten@isaac.nl",
         "avatarUrls":{
            "48x48":"https://jira.onpremise.org/secure/useravatar?ownerId=valentijn&avatarId=11101",
            "24x24":"https://jira.onpremise.org/secure/useravatar?size=small&ownerId=valentijn&avatarId=11101",
            "16x16":"https://jira.onpremise.org/secure/useravatar?size=xsmall&ownerId=valentijn&avatarId=11101",
            "32x32":"https://jira.onpremise.org/secure/useravatar?size=medium&ownerId=valentijn&avatarId=11101"
         },
         "displayName":"Valentijn Scholten",
         "active":"true",
         "timeZone":"Europe/Amsterdam"
      },
      "created":"2020-11-11T18:55:21.425+0100",
      "updated":"2020-11-11T18:55:21.425+0100"
   }
}
"""

    def __init__(self, *args, **kwargs):
        DojoTestCase.__init__(self, *args, **kwargs)

    def setUp(self):
        self.correct_secret = "12345"
        self.incorrect_secret = "1234567890"

    def test_webhook_get(self):
        response = self.client.get(reverse("jira_web_hook"))
        self.assertEqual(405, response.status_code, response.content[:1000])

    def test_webhook_jira_disabled(self):
        self.system_settings(enable_jira=False)
        response = self.client.post(reverse("jira_web_hook"))
        self.assertEqual(404, response.status_code, response.content[:1000])

    def test_webhook_disabled(self):
        self.system_settings(enable_jira=False, enable_jira_web_hook=False)
        response = self.client.post(reverse("jira_web_hook"))
        self.assertEqual(404, response.status_code, response.content[:1000])

    def test_webhook_invalid_content_type(self):
        self.system_settings(
            enable_jira=True,
            enable_jira_web_hook=True,
            disable_jira_webhook_secret=True,
        )
        response = self.client.post(reverse("jira_web_hook"))
        # 400 due to incorrect content_type
        self.assertEqual(400, response.status_code, response.content[:1000])

    def test_webhook_secret_disabled_no_secret(self):
        self.system_settings(
            enable_jira=True,
            enable_jira_web_hook=True,
            disable_jira_webhook_secret=True,
        )
        response = self.client.post(reverse("jira_web_hook"))
        # 400 due to incorrect content_type
        self.assertEqual(400, response.status_code, response.content[:1000])

    def test_webhook_secret_disabled_secret(self):
        self.system_settings(
            enable_jira=True,
            enable_jira_web_hook=True,
            disable_jira_webhook_secret=True,
        )
        response = self.client.post(
            reverse("jira_web_hook_secret", args=(self.incorrect_secret,))
        )
        # 400 due to incorrect content_type
        self.assertEqual(400, response.status_code, response.content[:1000])

    def test_webhook_secret_enabled_no_secret(self):
        self.system_settings(
            enable_jira=True,
            enable_jira_web_hook=True,
            disable_jira_webhook_secret=False,
            jira_webhook_secret=self.correct_secret,
        )
        response = self.client.post(reverse("jira_web_hook"))
        self.assertEqual(403, response.status_code, response.content[:1000])

    def test_webhook_secret_enabled_incorrect_secret(self):
        self.system_settings(
            enable_jira=True,
            enable_jira_web_hook=True,
            disable_jira_webhook_secret=False,
            jira_webhook_secret=self.correct_secret,
        )
        response = self.client.post(
            reverse("jira_web_hook_secret", args=(self.incorrect_secret,))
        )
        self.assertEqual(403, response.status_code, response.content[:1000])

    def test_webhook_secret_enabled_correct_secret(self):
        self.system_settings(
            enable_jira=True,
            enable_jira_web_hook=True,
            disable_jira_webhook_secret=False,
            jira_webhook_secret=self.correct_secret,
        )
        response = self.client.post(
            reverse("jira_web_hook_secret", args=(self.correct_secret,))
        )
        # 400 due to incorrect content_type
        self.assertEqual(400, response.status_code, response.content[:1000])

    def test_webhook_comment_on_finding(self):
        self.system_settings(
            enable_jira=True,
            enable_jira_web_hook=True,
            disable_jira_webhook_secret=False,
            jira_webhook_secret=self.correct_secret,
        )

        # finding 5 has a JIRA issue in the initial fixture for unit tests with id=2

        jira_issue = JIRA_Issue.objects.get(jira_id=2)
        finding = jira_issue.finding
        notes_count_before = finding.notes.count()

        response = self.client.post(
            reverse("jira_web_hook_secret", args=(self.correct_secret,)),
            self.jira_issue_comment_template_json,
            content_type="application/json",
        )

        jira_issue = JIRA_Issue.objects.get(jira_id=2)
        finding = jira_issue.finding
        notes_count_after = finding.notes.count()

        self.assertEqual(200, response.status_code, response.content[:1000])
        self.assertEqual(notes_count_after, notes_count_before + 1)

    # when a note is placed in defect dojo and sent to jira, it will trigger an incoming webhook request
    # we want to ignore that one because the incoming comment from jira is the comment that was placed in dojo
    def test_webhook_comment_on_finding_from_dojo_note(self):
        self.system_settings(
            enable_jira=True,
            enable_jira_web_hook=True,
            disable_jira_webhook_secret=False,
            jira_webhook_secret=self.correct_secret,
        )

        # finding 5 has a JIRA issue in the initial fixture for unit tests with id=2

        jira_issue = JIRA_Issue.objects.get(jira_id=2)
        finding = jira_issue.finding
        notes_count_before = finding.notes.count()

        body = json.loads(json.dumps(self.jira_issue_comment_template_json))
        body["comment"]["updateAuthor"]["name"] = "defect.dojo"
        body["comment"]["updateAuthor"]["displayName"] = "Defect Dojo"

        response = self.client.post(
            reverse("jira_web_hook_secret", args=(self.correct_secret,)),
            body,
            content_type="application/json",
        )

        jira_issue = JIRA_Issue.objects.get(jira_id=2)
        finding = jira_issue.finding
        notes_count_after = finding.notes.count()

        self.assertEqual(200, response.status_code)
        # incoming comment must be ignored
        self.assertEqual(notes_count_after, notes_count_before)

    # when a note is placed in defect dojo and sent to jira, it will trigger an incoming webhook request
    # we want to ignore that one because the incoming comment from jira is the comment that was placed in dojo
    # this time when name is not there, but with email (jira with sso?)
    def test_webhook_comment_on_finding_from_dojo_note_with_email(self):
        self.system_settings(
            enable_jira=True,
            enable_jira_web_hook=True,
            disable_jira_webhook_secret=False,
            jira_webhook_secret=self.correct_secret,
        )

        jira_issue = JIRA_Issue.objects.get(jira_id=2)
        finding = jira_issue.finding
        notes_count_before = finding.notes.count()

        # modify jira_instance to use email instead of name to perform testj
        jira_instance = jira_helper.get_jira_instance(finding)
        jira_instance.username = "defect.dojo@testme.com"
        jira_instance.save()

        body = json.loads(json.dumps(self.jira_issue_comment_template_json_with_email))
        body["comment"]["updateAuthor"]["emailAddress"] = "defect.dojo@testme.com"
        body["comment"]["updateAuthor"]["displayName"] = "Defect Dojo"

        response = self.client.post(
            reverse("jira_web_hook_secret", args=(self.correct_secret,)),
            body,
            content_type="application/json",
        )

        jira_issue = JIRA_Issue.objects.get(jira_id=2)
        finding = jira_issue.finding
        notes_count_after = finding.notes.count()

        # reset jira_instance to use name to avoid confusion for potential later tests
        jira_instance = jira_helper.get_jira_instance(finding)
        jira_instance.username = "defect.dojo"
        jira_instance.save()

        self.assertEqual(200, response.status_code)
        # incoming comment must be ignored
        self.assertEqual(notes_count_after, notes_count_before)

    def test_webhook_comment_on_finding_jira_under_path(self):
        self.system_settings(
            enable_jira=True,
            enable_jira_web_hook=True,
            disable_jira_webhook_secret=False,
            jira_webhook_secret=self.correct_secret,
        )

        # finding 5 has a JIRA issue in the initial fixture for unit tests with id=2

        body = json.loads(json.dumps(self.jira_issue_comment_template_json))
        body["comment"][
            "self"
        ] = "http://www.testjira.com/my_little_happy_path_for_jira/rest/api/2/issue/2/comment/456843"

        jira_issue = JIRA_Issue.objects.get(jira_id=2)
        finding = jira_issue.finding
        notes_count_before = finding.notes.count()

        response = self.client.post(
            reverse("jira_web_hook_secret", args=(self.correct_secret,)),
            self.jira_issue_comment_template_json,
            content_type="application/json",
        )

        jira_issue = JIRA_Issue.objects.get(jira_id=2)
        finding = jira_issue.finding
        notes_count_after = finding.notes.count()

        self.assertEqual(200, response.status_code, response.content[:1000])
        self.assertEqual(notes_count_after, notes_count_before + 1)

    def test_webhook_comment_on_engagement(self):
        self.system_settings(
            enable_jira=True,
            enable_jira_web_hook=True,
            disable_jira_webhook_secret=False,
            jira_webhook_secret=self.correct_secret,
        )

        # 333 = engagement
        body = json.loads(json.dumps(self.jira_issue_comment_template_json))
        body["comment"][
            "self"
        ] = "http://www.testjira.com/rest/api/2/issue/333/comment/456843"

        response = self.client.post(
            reverse("jira_web_hook_secret", args=(self.correct_secret,)),
            body,
            content_type="application/json",
        )
        print(response.content)

        self.assertEqual(200, response.status_code, response.content[:1000])
        self.assertEqual(b"Comment for engagement ignored", response.content)

    def test_webhook_update_engagement(self):
        self.system_settings(
            enable_jira=True,
            enable_jira_web_hook=True,
            disable_jira_webhook_secret=False,
            jira_webhook_secret=self.correct_secret,
        )

        # 333 = engagement
        body = json.loads(self.jira_issue_update_template_string)
        body["issue"]["id"] = 333

        response = self.client.post(
            reverse("jira_web_hook_secret", args=(self.correct_secret,)),
            body,
            content_type="application/json",
        )

        self.assertEqual(200, response.status_code, response.content[:1000])
        self.assertEqual(b"Update for engagement ignored", response.content)

    def test_webhook_comment_no_finding_no_engagement(self):
        self.system_settings(
            enable_jira=True,
            enable_jira_web_hook=True,
            disable_jira_webhook_secret=False,
            jira_webhook_secret=self.correct_secret,
        )

        # 666 = nothing attached to JIRA_Issue
        body = json.loads(json.dumps(self.jira_issue_comment_template_json))
        body["comment"][
            "self"
        ] = "http://www.testjira.com/rest/api/2/issue/666/comment/456843"

        response = self.client.post(
            reverse("jira_web_hook_secret", args=(self.correct_secret,)),
            body,
            content_type="application/json",
        )

        self.assertEqual(404, response.status_code, response.content[:1000])

    def test_webhook_update_no_finding_no_engagement(self):
        self.system_settings(
            enable_jira=True,
            enable_jira_web_hook=True,
            disable_jira_webhook_secret=False,
            jira_webhook_secret=self.correct_secret,
        )

        # 666 = nothing attached to JIRA_Issue
        body = json.loads(self.jira_issue_update_template_string)
        body["issue"]["id"] = 999

        response = self.client.post(
            reverse("jira_web_hook_secret", args=(self.correct_secret,)),
            body,
            content_type="application/json",
        )

        self.assertEqual(404, response.status_code, response.content[:1000])

    def test_webhook_comment_no_jira_issue_at_all(self):
        self.system_settings(
            enable_jira=True,
            enable_jira_web_hook=True,
            disable_jira_webhook_secret=False,
            jira_webhook_secret=self.correct_secret,
        )

        # 666 = nothing attached to JIRA_Issue
        body = json.loads(json.dumps(self.jira_issue_comment_template_json))
        body["comment"][
            "self"
        ] = "http://www.testjira.com/rest/api/2/issue/999/comment/456843"

        response = self.client.post(
            reverse("jira_web_hook_secret", args=(self.correct_secret,)),
            body,
            content_type="application/json",
        )

        self.assertEqual(404, response.status_code, response.content[:1000])

    def test_webhook_update_no_jira_issue_at_all(self):
        self.system_settings(
            enable_jira=True,
            enable_jira_web_hook=True,
            disable_jira_webhook_secret=False,
            jira_webhook_secret=self.correct_secret,
        )

        # 666 = nothing attached to JIRA_Issue
        body = json.loads(self.jira_issue_update_template_string)
        body["issue"]["id"] = 666

        response = self.client.post(
            reverse("jira_web_hook_secret", args=(self.correct_secret,)),
            body,
            content_type="application/json",
        )

        self.assertEqual(404, response.status_code, response.content[:1000])

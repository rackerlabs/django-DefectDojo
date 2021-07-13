---
title: "Parsers"
description: "How to contribute to parsers"
draft: false
weight: 1
---

{{% alert title="Information" color="info" %}}
All commands assume that you're located at the root of the django-DefectDojo cloned repo.
{{% /alert %}}

## Pre-requisites

- You have forked https://github.com/DefectDojo/django-DefectDojo and cloned locally.
- Checkout `dev` and make sure you're up to date with the latest changes.
- It's advised that you create a dedicated branch for your development, such as `git checkout -b parser-name` yet that's up to you.

It is probably easier to use the docker-compose stack (and benefit from the hot-reload capbility for uWSGI).
Set up your environment to use the debug environment, such as:

`$ docker/setEnv.sh debug`

Please have a look at [DOCKER.md](https://github.com/DefectDojo/django-DefectDojo/blob/master/DOCKER.md) for more details.

### Docker images
You'd want to build your docker images locally, and eventually pass in your local user's `uid` to be able to write to the image (handy for database migration files). Assuming your user's `uid` is `1000`, then:

{{< highlight bash >}}
$ docker-compose build --build-arg uid=1000
{{< /highlight >}}

## Which files do you need to modify?

| File                                          | Purpose
|-------                                        |--------
|`dojo/tools/<parser_dir>/__init__.py`          | Empty file for class initialization
|`dojo/tools/<parser_dir>/parser.py`            | The meat. This is where you write your actual parser
|`dojo/unittests/scans/<parser_dir>/{many_vulns,no_vuln,one_vuln}.json` | Sample files containing meaningful data for unit tests. The minimal set.
|`dojo/settings/settings.dist.py`               | If you want to use a modern hashcode based deduplication algorithm


## Template Generator

Utilze the [template](https://github.com/DefectDojo/cookiecutter-scanner-parser)  parser to quickly generate the files required. To get started you will need to install [cookiecutter](https://github.com/cookiecutter/cookiecutter).

{{< highlight bash >}}
$ pip install cookiecutter
{{< /highlight >}}

Then generate your scanner parser from the root of django-DefectDojo:

{{< highlight bash >}}
$ cookiecutter https://github.com/DefectDojo/cookiecutter-scanner-parser
{{< /highlight >}}

Read [more](https://github.com/DefectDojo/cookiecutter-scanner-parser) on the template configuration variables.

## Things to pay attention to

Here is a list of advise that will make your parser future proof.

### Do not parse URLs by hand

We use 2 modules to handle endpoints:
 - `hyperlink` 
 - `dojo.models` with a specific class to handle processing around URLs to create endpoints `Endpoint`.

All the existing parser use the same code to parse URL and create endpoints.
Using `Endpoint.from_uri()` is the best way to create endpoints.
If you really need to parse an URL, use `hyperlink` module.

Good example:

```python
    if "url" in item:
        endpoint = Endpoint.from_uri(item["url"])
        finding.unsaved_endpoints = [endpoint]
```

Very bad example:

```python
    u = urlparse(item["url"])
    endpoint = Endpoint(host=u.host)
    finding.unsaved_endpoints = [endpoint]
```

### Not all attributes are mandatory

Parsers may have many fields, out of which many of them may be optional.
It better to not set attribute if you don't have data instead of filling with values like `NA`, `No data` etc...

Check class `dojo.models.Finding` 

### Data could be missing in the source report

Always make sure you include checks to avoid potential `KeyError` errors (e.g. field does not exist), for those fields you are not absolutely certain will always be in file that will get uploaded. These translate to 500 error, and do not look good.

Good example:

```python
   if "mykey" in data:
       finding.cve = data["mykey"]
```

### Do not parse CVSS by hand (vector, score or severity)

Data can have `CVSS` vectors or scores. Don't try to write your own CVSS score algorithm.
For parser, we rely on module `cvss`.

It's easy to use and will make the parser aligned with the rest of the code.

Example of use:

```python
from cvss.cvss3 import CVSS3
import cvss.parser
vectors = cvss.parser.parse_cvss_from_text("CVSS:3.0/S:C/C:H/I:H/A:N/AV:P/AC:H/PR:H/UI:R/E:H/RL:O/RC:R/CR:H/IR:X/AR:X/MAC:H/MPR:X/MUI:X/MC:L/MA:X")
if len(vectors) > 0 and type(vectors[0]) == CVSS3:
    print(vectors[0].severities())  # this is the 3 severities

    cvssv3 = vectors[0].clean_vector()
    severity = vectors[0].severities()[0]
    vectors[0].compute_base_score()
    cvssv3_score = vectors[0].scores()[0]
    print(severity)
    print(cvssv3_score)
```

Good example:

```python
vectors = cvss.parser.parse_cvss_from_text(item['cvss_vect'])
if len(vectors) > 0 and type(vectors[0]) == CVSS3:
    finding.cvss = vectors[0].clean_vector()
    finding.severity = vectors[0].severities()[0]  # if your tool does generate severity
```

Bad example (DIY):

```python
    def get_severity(self, cvss, cvss_version="2.0"):
        cvss = float(cvss)
        cvss_version = float(cvss_version[:1])
        # If CVSS Version 3 and above
        if cvss_version >= 3:
            if cvss > 0 and cvss < 4:
                return "Low"
            elif cvss >= 4 and cvss < 7:
                return "Medium"
            elif cvss >= 7 and cvss < 9:
                return "High"
            elif cvss >= 9:
                return "Critical"
            else:
                return "Informational"
        # If CVSS Version prior to 3
        else:
            if cvss > 0 and cvss < 4:
                return "Low"
            elif cvss >= 4 and cvss < 7:
                return "Medium"
            elif cvss >= 7 and cvss <= 10:
                return "High"
            else:
                return "Informational"
```

## Deduplication algorithm

By default a new parser uses the 'legacy' deduplication algorithm documented at https://defectdojo.github.io/django-DefectDojo/usage/features/#deduplication-algorithms

## Unit tests

Each parser must have unit tests, at least to test for 0 vuln, 1 vuln and many vulns. You can take a look at how other parsers have them for starters. The more quality tests, the better.

It's important to add checks on attributes of findings.
For ex:

```python
        with self.subTest(i=0):
            finding = findings[0]
            self.assertEqual("test title", finding.title)
            self.assertEqual(True, finding.active)
            self.assertEqual(True, finding.verified)
            self.assertEqual(False, finding.duplicate)
            self.assertIn(finding.severity, Finding.SEVERITIES)
            self.assertEqual("CVE-2020-36234", finding.cve)
            self.assertEqual(261, finding.cwe)
            self.assertEqual("CVSS:3.1/AV:N/AC:L/PR:H/UI:R/S:C/C:L/I:L/A:N", finding.cvssv3)
            self.assertIn("security", finding.tags)
            self.assertIn("network", finding.tags)
            self.assertEqual("3287f2d0-554f-491b-8516-3c349ead8ee5", finding.unique_id_from_tool)
            self.assertEqual("TEST1", finding.vuln_id_from_tool)
```

### Test database

To test your unit tests locally, you first need to grant some rights. Get your MySQL root password from the 
docker-compose logs by looking for the entry ```[Note] [Entrypoint]: GENERATED ROOT PASSWORD:```, login as root and issue the following commands:

{{< highlight mysql >}}
MYSQL> grant all privileges on test_defectdojo.* to defectdojo@'%';
MYSQL> flush privileges;
{{< /highlight >}}

### Run your tests

This local command will launch the unit test for your new parser

{{< highlight bash >}}
$ docker-compose exec uwsgi bash -c 'python manage.py test dojo.unittests.tools.<your_unittest_py_file>.<main_class_name> -v2'
{{< /highlight >}}

Example for the blackduck hub parser:

{{< highlight bash >}}
$ docker-compose exec uwsgi bash -c 'python manage.py test dojo.unittests.tools.test_blackduck_csv_parser.TestBlackduckHubParser -v2'
{{< /highlight >}}

{{% alert title="Information" color="info" %}}
If you want to run all unit tests, simply run `$ docker-compose exec uwsgi bash -c 'python manage.py test dojo.unittests -v2'`
{{% /alert %}}

### Endpoint validation

Some types of parsers create a list of endpoints that are vulnerable (they are stored in `finding.unsaved_endpoints`). DefectDojo requires storing endpoints in a specific format (which follow RFCs). Endpoints that do not follow this format can be stored but they will be marked as broken (red flag 🚩in UI). To be sure your parse store endpoints in the correct format run the `.clean()` function for all endpoints in unit tests

```python
findings = parser.get_findings(testfile, Test())
for finding in findings:
    for endpoint in finding.unsaved_endpoints:
        endpoint.clean()
```

## Other files that could be involved

### Change to the model

In the event where you'd have to change the model, e.g. to increase a database column size to accomodate a longer string of data to be saved
* Change what you need in `dojo/models.py`
* Create a new migration file in dojo/db_migrations by running and including as part of your PR

    {{< highlight bash >}}
    $ docker-compose exec uwsgi bash -c 'python manage.py makemigrations -v2'
    {{< /highlight >}}

### Accept a different type of file to upload

If you want to be able to accept a new type of file for your parser, take a look at `dojo/forms.py` around line 436 (at the time of this writing) or locate the 2 places (for import and re-import) where you find the string `attrs={"accept":`.

Formats currently accepted: .xml, .csv, .nessus, .json, .html, .js, .zip.

### A need for more than just the parser.py

Of course, nothing prevents you from having more files than the `parser.py` file. It's python :-)

## Pull request examples

If you want to take a look at previous parsers that are now part of DefectDojo, take a look at https://github.com/DefectDojo/django-DefectDojo/pulls?q=is%3Apr+sort%3Aupdated-desc+label%3A%22Import+Scans%22+is%3Aclosed

## Update the import page documentation

Please update [`docs/content/en/integrations/import.md`] with the details of your new parser.

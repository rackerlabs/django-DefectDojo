#!/usr/bin/python3
import time
import collections
import socket
from zapv2 import ZAPv2
from urllib.parse import urlparse
from prettytable import PrettyTable
import re


class Main:
    if __name__ == "__main__":

        address = "127.0.0.1"
        port = 8080

        print(
            (
                "Checking if ZAP is running, connecting to ZAP on http://"
                + address
                + ":"
                + str(port)
            )
        )
        s = socket.socket()

        try:
            s.connect((address, port))
        except socket.error as e:
            print("Error connecting to ZAP, exiting.")
            sys.exit(0)

        zap = ZAPv2(
            proxies={"http": "http://127.0.0.1:8080", "https": "http://127.0.0.1:8080"}
        )
        apikey = ""

        # user_input_obj = User_Input() #Creating object for class User_Input
        targetURL = "http://dojo:8000"

        # targetURLregex = "\Q" + targetURL + "\E.*"  # Regular expression to be considered within our context.
        # The above line is flake8 violation as \Q and \E are not supported by python
        targetURLregex = re.escape(targetURL)

        # Defining context name as hostname from URL and creating context using it.
        contextname = urlparse(targetURL).netloc
        print(("Context Name: " + contextname))

        # Step1: Create context
        contextid = zap.context.new_context(contextname, apikey)
        print(("ContextID: " + contextid))

        # Step2: Include in the context
        result = zap.context.include_in_context(contextname, targetURLregex, apikey)
        print(("URL regex defined in context: " + result))

        # Step3: Session Management - Default is cookieBasedSessionManagement
        result = zap.sessionManagement.set_session_management_method(
            contextid, "cookieBasedSessionManagement", None, apikey
        )
        print(("Session method defined: " + result))

        loginUrl = "http://os.environ['DD_BASE_URL']/login"
        # loginUrlregex = "\Q" + loginUrl + "\E.*"
        # The above line is flake8 violation as \Q and \E are not supported by python
        loginURLregex = re.escape(loginURL)
        result = zap.context.exclude_from_context(contextname, ".*logout.*", apikey)
        result = zap.context.exclude_from_context(contextname, ".*/static/.*", apikey)

        # Wait for passive scanning to complete
        while int(zap.pscan.records_to_scan) > 0:
            print(("Records to passive scan : " + zap.pscan.records_to_scan))
            time.sleep(15)
        print("Passive scanning complete")

        print(("Actively Scanning target " + targetURL))
        ascan_id = zap.ascan.scan(
            targetURL, None, None, None, None, None, apikey
        )  # Can provide more options for active scan here instead of using None.
        while int(zap.ascan.status(ascan_id)) < 100:
            print(("Scan progress %: " + zap.ascan.status(ascan_id)))
            time.sleep(15)

        print("Scan completed")

        # Report the results
        sort_by_url = collections.defaultdict(list)
        for alert in zap.core.alerts():
            sort_by_url[alert["url"]].append(
                {"risk": alert["risk"], "alert": alert["alert"]}
            )

        summary = PrettyTable(["Risk", "Count"])
        summary.padding_width = 1
        summary.align = "l"
        info = 0
        low = 0
        medium = 0
        high = 0

        for url in sort_by_url:

            for details in sort_by_url[url]:
                if details["risk"] == "Informational":
                    info = info + 1
                if details["risk"] == "Low":
                    low = low + 1
                if details["risk"] == "Medium":
                    medium = medium + 1
                if details["risk"] == "High":
                    high = high + 1

        summary.add_row(["Informational", info])
        summary.add_row(["Low", low])
        summary.add_row(["Medium", medium])
        summary.add_row(["High", high])
        print(summary)

        for url in sort_by_url:
            print()
            print(url)

            results = PrettyTable(["Risk", "Description"])
            results.padding_width = 1
            results.align = "l"
            results.sortby = "Risk"

            for details in sort_by_url[url]:
                results.add_row([details["risk"], details["alert"]])

            print(results)

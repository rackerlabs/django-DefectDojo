import queue
from datetime import datetime
import sys
import threading
from ast import literal_eval

from django.core.mail import send_mail
from django.core.management import call_command
from django.core.management.base import BaseCommand
from nmap import PortScannerAsync, PortScannerError
from pytz import timezone

from dojo.models import Scan, Product, ScanSettings, IPScan
from django.conf import settings
from dojo.utils import get_system_setting

locale = timezone(get_system_setting("time_zone"))


"""
Authors: Fatimah and Michael
A script that scans a scheduled input of hosts for open ports and emails the
results of the scan to the product's POC.
"""


class Command(BaseCommand):
    help = (
        "Details:\n\tRuns nmap scans\n\nArguments:"
        + "\n\tWeekly\n\tMonthly\n\tQuarterly"
    )

    def add_arguments(self, parser):
        parser.add_argument("type")

    def handle(self, *args, **options):
        type = options["type"]

        # Scan the host and add the results of the scan to the host informaiton
        def runScan(prod_id, p_dict):
            ipScan_queue = queue.Queue(50)
            for host in p_dict:
                current_scan = Scan.objects.get(id=p_dict[host]["scan_id"])
                if not current_scan.date:
                    current_scan.date = locale.localize(datetime.today())

                # For each host, save the IPScan and the date to the scan
                # to the db

                ipScan_queue.put((host, p_dict[host]))
                ipscan_thread = threadedIPScan(ipScan_queue)
                ipscan_thread.setDaemon(True)
                ipscan_thread.start()

            ipScan_queue.join()

            # Compare the results to the expected ports and email results if
            # necessary
            product = Product.objects.get(id=prod_id).name
            msg = "Hello, \n\nA port scan of the product " + product
            msg += " was performed on " + locale.normalize(current_scan.date).strftime(
                "%A %B %d, %Y at %I:%M:%S %p"
            )
            msg += "\nThe results of the scan show that the following ip "
            msg += "addresses have the following ports open: \n\n"

            for host in p_dict:
                msg += str(host) + ": \n"
                for p in p_dict[host]["result"]:
                    msg += str(p) + " \n"

                scans_same_setting = Scan.objects.filter(
                    scan_settings=current_scan.scan_settings
                )
                diff = p_dict[host]["result"] - p_dict[host]["expected"]
                if diff and len(scans_same_setting) > 1:
                    msg += "\nThese ports appear in this scan but were not "
                    msg += "open in the previous scan:\n "
                    msg += "****** Please ensure that these ports are open if "
                    msg += "and only if you have meant it that way ******\n"
                    msg += str(host) + ": \n"
                    for d in diff:
                        msg += str(d) + " \n"

            msg += "\nYou are receiving this email because you have signed up "
            msg += "for a port scan on the product security test dojo.\n"
            msg += "\nFor any questions please email "
            msg += settings.PORT_SCAN_CONTACT_EMAIL + "\n"
            msg += "Thanks,\nThe "
            msg += get_system_setting("team_name")
            msg += " Team"
            email_to = current_scan.scan_settings.email

            send_mail(
                get_system_setting("team_name") + " Port Scan Report",
                msg,
                settings.PORT_SCAN_RESULT_EMAIL_FROM,
                [email_to],
                fail_silently=False,
            )

        # Second
        def runIPScan(host, service_dict):
            host = host.strip()
            try:
                nm = PortScannerAsync()
            except PortScannerError:
                print(("Nmap not found", sys.exc_info()[0]))
                sys.exit(0)
            except:
                print(("Unexpected error:", sys.exc_info()[0]))
                sys.exit(0)

            def callback_result(host, scan_result, service_dict=service_dict):
                host = str(host).strip()
                try:
                    current_scan = Scan.objects.get(id=service_dict["scan_id"])
                    p = current_scan.scan_settings.protocol.lower()
                    openTCP = list(scan_result["scan"][host][p].keys())
                    # Save the open ports found by the scan to the dict
                    service_dict["result"] = openTCP
                    # enumerate the found port information to save to the db
                    services = "["
                    for port in service_dict["result"]:
                        services += "(" + str(port) + ",'" + p + "','"
                        services += str(scan_result["scan"][host][p][port]["state"])
                        services += "','"
                        services += str(scan_result["scan"][host][p][port]["name"])
                        services += "',),"
                    services += "]"
                except:
                    services = []
                    current_scan = Scan.objects.get(id=service_dict["scan_id"])
                IPScan.objects.create(
                    address=host, services=services, scan=current_scan
                )
                current_scan.status = "Completed"
                current_scan.save()

            scan = Scan.objects.get(id=service_dict["scan_id"])
            # Run the Nmap Scan
            # what kind of scan?
            if scan.scan_settings.protocol == "TCP":
                nm.scan(str(host), arguments="-T4 -p-", callback=callback_result)
                scan.status = "Running"
            elif scan.scan_settings.protocol == "UDP":
                nm.scan(str(host), arguments="-T4 -sU -p-", callback=callback_result)
                scan.status = "Running"
            scan.save()
            while nm.still_scanning():
                # this is needed or else IPScan wont have been saved
                nm.wait(2)

            scan_results = set()
            try:
                scan_results = set(
                    literal_eval(
                        IPScan.objects.get(
                            address=host,
                            scan=Scan.objects.get(id=service_dict["scan_id"]),
                        ).services
                    )
                )
                scan_results = [
                    str(x[0]) + "/" + str(x[1]) + ": " + str(x[3]) for x in scan_results
                ]
            except:
                scan.status = "Failed"
                scan.save()
                pass

            service_dict["result"] = set(scan_results)

        """
            The scanning is done by two tiers of threading to efficiently scan
            multiple ipaddresses
            threadedScan = First set of threads spawned by the Main thread.
                Each assigned to a product in the requested list of scans.
                Target the runScan.
            threadedIPScan = Second set of threads spawned by each threadedScan
                Each runs an nmap scan for an ipadress. Target runIPScan.
        """

        class threadedScan(threading.Thread):
            def __init__(self, scan_queue):
                threading.Thread.__init__(self)
                self.scan_queue = scan_queue

            def run(self):
                (prod_id, p_dict) = self.scan_queue.get()
                runScan(prod_id, p_dict)
                self.scan_queue.task_done()

        class threadedIPScan(threading.Thread):
            def __init__(self, ipScan_queue):
                threading.Thread.__init__(self)
                self.ipScan_queue = ipScan_queue

            def run(self):
                (host, service_dict) = self.ipScan_queue.get()
                runIPScan(host, service_dict)
                self.ipScan_queue.task_done()

        """
            Scans are performed on a Weekly, Monthly, or Quarterly bases. The
            target frequency is specified by the cron job scheduler.
        """
        if not options:
            print(
                "Must specify an argument: Weekly, Monthly, Quarterly, or ID",
                " of Scan Settings to use.",
            )
            sys.exit(0)
        if type in ["Weekly", "Monthly", "Quarterly"] or type.isdigit():
            pass
        else:
            print(("Unexpected parameter: " + str(args[0])))
            print(
                "\nMust specify an argument: Weekly, Monthly, Quarterly",
                " or ID of Scan Settings to use.",
            )
            sys.exit(0)

        if type.isdigit():
            scSettings = ScanSettings.objects.filter(id=type)
        else:
            scSettings = ScanSettings.objects.filter(frequency=type)

        if len(scSettings) <= 0:
            print("No scan settings found with parameter specified.")
            sys.exit(0)
        """
            Main thread creates a dictionary formatted:
                {prod_id: {hosts: {scan_id, expected, result}}}
        """
        scan_queue = queue.Queue()
        host_dict = {}
        for s in scSettings:
            try:
                #  do we have a baseline set
                baseline_scan = Scan.objects.filter(
                    scan_settings_id=s.id, protocol=s.protocol, baseline=True
                )
                if len(baseline_scan):
                    baseline_scan = baseline_scan[0]  # get the first scan
                else:
                    # no baseline, lets use the latest completed one
                    baseline_scan = Scan.objects.filter(
                        scan_settings_id=s.id, protocol=s.protocol, status="Completed"
                    ).order_by("-date")[0]
                most_recent_ipscans = IPScan.objects.filter(scan=baseline_scan)
                first_scan = False
                if len(most_recent_ipscans) == 0:
                    first_scan = True
            except:  # No previous scans for this scan setting
                first_scan = True
            # Create a Scan for each requested Scan (Scan Setting)
            scan = Scan.objects.create(
                scan_settings_id=s.id,
                protocol=s.protocol,
                date=locale.localize(datetime.today()),
            )
            prod_id = str(s.product_id)
            list_addresses = s.addresses.strip().split(",")
            for line in list_addresses:
                addr = line.strip()
                key = "%s_%s_%s" % (prod_id, addr, s.protocol)
                host_dict.update(
                    {
                        key: {
                            addr: {
                                "expected": set([]),
                                "scan_id": str(scan.id),
                                "result": set([]),
                            }
                        }
                    }
                )

                if first_scan:
                    host_dict.update(
                        {
                            key: {
                                addr: {
                                    "expected": set([]),
                                    "scan_id": str(scan.id),
                                    "result": set([]),
                                }
                            }
                        }
                    )
                else:
                    try:
                        most_recent_ports = [
                            str(x[0]) + "/" + str(x[1]) + ": " + str(x[3])
                            for x in literal_eval(
                                most_recent_ipscans.get(address=addr).services
                            )
                        ]
                    except:
                        most_recent_ports = []
                    if len(most_recent_ports) > 0:
                        for port in most_recent_ports:
                            try:
                                host_dict[key][addr]["expected"].add(port)
                            except KeyError:
                                host_dict.update(
                                    {
                                        key: {
                                            addr: {
                                                "expected": set([port]),
                                                "scan_id": str(scan.id),
                                                "result": set([]),
                                            }
                                        }
                                    }
                                )

        for (prod_id, p_dict) in list(host_dict.items()):
            pid = prod_id.split("_")[0]
            scan_queue.put((pid, p_dict))
            t = threadedScan(scan_queue)
            t.setDaemon(True)
            t.start()

        scan_queue.join()


def run_on_deman_scan(sid):
    call_command("run_scan", sid)
    return True

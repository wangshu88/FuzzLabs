import os
import cmd
import sys
import json
import copy
import pprint
import base64
import inspect
import httplib

from OpenSSL import crypto, SSL
from time import gmtime, mktime
from os.path import exists, join

from classes.Utils import Utils
from classes.State import State
from classes.Job import Job

# -----------------------------------------------------------------------------
#
# -----------------------------------------------------------------------------

class CliConfigEngine(cmd.Cmd):
    ruler = '-'
    prompt = 'fuzzlabs(engines) > '

    # -------------------------------------------------------------------------
    #
    # -------------------------------------------------------------------------

    def __init__(self, config, completekey='tab', stdin = None, stdout = None):
        cmd.Cmd.__init__(self, completekey, stdin, stdout)
        self.config = config
        self.pp     = pprint.PrettyPrinter(indent=2, width=80)

    # -------------------------------------------------------------------------
    #
    # -------------------------------------------------------------------------

    def get_engine_by_id(self, id):
        engines = self.config.get('data').get('engines')
        if not engines or len(list(engines)) == 0:
            print "[i] no engines registered"
            return None
        engine = engines.get(id)
        if not engine:
            print "[i] no engine registered with id '%s'" % id
            return None
        return engine

    # -------------------------------------------------------------------------
    #
    # -------------------------------------------------------------------------

    def do_shell(self, args):
        'Execute operating system command.'
        os.system(args)

    # -------------------------------------------------------------------------
    #
    # -------------------------------------------------------------------------

    def do_exit(self, args):
        return True

    # -------------------------------------------------------------------------
    #
    # -------------------------------------------------------------------------

    def callback_acl_init(self, status, reason, data, engine):
        if (status != 200):
            print "[e] failed to add engine: %s" % data.get('message')

    # -------------------------------------------------------------------------
    #
    # -------------------------------------------------------------------------

    def callback_get_api_key(self, status, reason, data, engine):
        if (status != 200):
            print "[e] failed to add engine: %s" % data.get('message')
        else:
            apikey = data.get('apikey')
            if not apikey:
                print "[e] failed to add engine: %s" %\
                      "no API key in response"
                return

            if not self.config.get('data').get('engines'):
                self.config.get('data')['engines'] = {}
            id = Utils.generate_name()
            self.config.get('data').get('engines')[id] = {
                "address": engine.get('address'),
                "port": engine.get('port'),
                "apikey": apikey
            }
            self.config.save()

    # -------------------------------------------------------------------------
    #
    # -------------------------------------------------------------------------

    def do_add(self, args):
        initialization = [
            {"method": "GET", "uri": "/setup/acl",
             "callback": self.callback_acl_init},
            {"method": "GET", "uri": "/setup/apikey",
             "callback": self.callback_get_api_key}
        ]

        args = args.split(" ")
        if len(args) < 1:
            print "[e] invalid syntax"
            return
        address = args[0]
        port = 26000
        if len(args) == 2:
            try:
                port = int(args[1])
            except:
                print "[e] invalid port number"
                return

        for robject in initialization:
            rc = Utils.engine_request(self.config,
                                     address,
                                     port,
                                     robject,
                                     None).get('status')
            if rc != 200: break

    # -------------------------------------------------------------------------
    #
    # -------------------------------------------------------------------------

    def help_add(self):
        print "\nThe add command can be used to add a new engine.\n\n" +\
              "Syntax: add <address> [ port ]\n\n" +\
              "address: the IP address of the engine\n" +\
              "port:    the port number the engine is listening on (default: 26000)\n\n" +\
              "For the command to be successful The engine has to be running at\n" +\
              "the time of issuing the command. The engine has to run with a stock\n" +\
              "configuration as adding the engine involves automatic, initial\n" +\
              "engine configuration.\n"

    # -------------------------------------------------------------------------
    #
    # -------------------------------------------------------------------------

    def do_list(self, args):
        'List registered engines.'
        engines = self.config.get('data').get('engines')
        if not engines or len(list(engines)) == 0:
            print "[i] no engines registered"
            return

        print
        for engine in engines:
            status = "unknown"
            engine_data = self.config.get('data').get('engines')[engine]

            rc = Utils.engine_request(self.config,
                                     engine_data['address'],
                                     engine_data['port'], 
            {
                "method": "GET",
                "uri": "/management/ping?apikey=" + engine_data['apikey'],
                "data": None
            }, engine)
            if rc:
                if rc.get('status') == 200 and \
                   rc.get('data').get('message') == "pong":
                    status = "active"

            ssls = "Yes" if engine_data.get('ssl') == 1 else "No"
            print "id: " + engine
            print "  %-10s: %-40s" % ("Address", engine_data['address'])
            print "  %-10s: %-40s" % ("Port", str(engine_data['port']))
            print "  %-10s: %-40s" % ("SSL", ssls)
            print "  %-10s: %-40s" % ("Api key", str(engine_data['apikey']))
            print "  %-10s: %-40s" % ("Status", status)
            print

    # -------------------------------------------------------------------------
    #
    # -------------------------------------------------------------------------

    def do_shutdown(self, args):
        engine = self.get_engine_by_id(args)
        if not engine: return

        rc = Utils.engine_request(self.config,
                                 engine['address'],
                                 engine['port'],
        {
            "method": "GET",
            "uri": "/management/shutdown?apikey=" + engine['apikey'],
            "data": None
        }, engine)
        if rc:
            if rc.get('status') == 200:
                print "[i] engine shut down"

    # -------------------------------------------------------------------------
    #
    # -------------------------------------------------------------------------

    def help_shutdown(self):
        print "\nThe shutdown command can be used to shut down the engine.\n\n" +\
              "Syntax: shutdown <engine id>\n"

    # -------------------------------------------------------------------------
    #
    # -------------------------------------------------------------------------

    def do_remove(self, args):
        args = args.split(" ")
        if len(args) != 2:
            print "[e] syntax error"
            return

        engine = self.get_engine_by_id(args[1])
        if not engine: return

        uri = None
        if args[0] == "abandon":
            uri = "/management/remove?terminate=false&apikey=" + engine['apikey']
        elif args[0] == "terminate":
            uri = "/management/remove?terminate=true&apikey=" + engine['apikey']
        else:
            print "[e] invalid option '%s'" % args[0]
            return

        rc = Utils.engine_request(self.config,
                                 engine.get('address'),
                                 engine.get('port'),
        {
            "method": "GET",
            "uri": uri,
            "data": None
        }, args[1])
        if rc:
            if rc.get('status') == 200:
                engines_list = copy.deepcopy(self.config.get('data').get('engines'))
                for engine in engines_list:
                    if engine == args[1]:
                        self.config.get('data').get('engines').pop(engine)
                self.config.save()
                print "[i] engine removed"
            else:
                print "[i] failed to remove engine: %s" %\
                      rc.get('data').get('message')

    # -------------------------------------------------------------------------
    #
    # -------------------------------------------------------------------------

    def help_remove(self):
        print "\nUnregisters the engine.\n\n" +\
              "Syntax: remove [ abandon | terminate ] <engine id>\n\n" +\
              "abandon:   zeroes out the API key and ACL of the engine configuration,\n" +\
              "           removes the engine from the client database, but leaves\n" +\
              "           the engine running. In this state, other clients can take\n" +\
              "           over the engine.\n" +\
              "terminate: same as abandon, but instead of leaving the engine running\n" +\
              "           it will be completely shut down.\n"

    # -------------------------------------------------------------------------
    #
    # -------------------------------------------------------------------------

    def check_local_certificates(self):
        has_certs = True
        if not self.config.get('data').get('security'):
            self.config.get('data')['security'] = {}
            has_certs = False

        if not self.config.get('data').get('security').get('ssl'):
            self.config.get('data').get('security')['ssl'] = {}
            has_certs = False

        if not self.config.get('data').get('security').get('ssl').get('certificate_file'):
            self.config.get('data').get('security').get('ssl')['certificate_file'] = "client.crt"
            has_certs = False

        if not self.config.get('data').get('security').get('ssl').get('key_file'):
            self.config.get('data').get('security').get('ssl')['key_file'] = "client.key"
            has_certs = False

        if not self.config.get('root'):
            print "[e] could not determine FuzzLabs client root path, aborting."
            return

        cf = self.config.get('root') + "/config/certificates/" +\
             self.config.get('data').get('security').get('ssl').get('certificate_file')

        kf = self.config.get('root') + "/config/certificates/" +\
             self.config.get('data').get('security').get('ssl').get('key_file')

        self.config.save()

        if not exists(cf) or not exists(kf):
            has_certs = False
        return has_certs

    # -------------------------------------------------------------------------
    #
    # -------------------------------------------------------------------------

    def create_certificate(self, engine_id, cf, kf):
        k = crypto.PKey()
        k.generate_key(crypto.TYPE_RSA, 2048)

        c = crypto.X509()
        c.get_subject().C = "UK"
        c.get_subject().ST = "London"
        c.get_subject().L = "London"
        c.get_subject().O = "DCNWS"
        c.get_subject().OU = "DCNWS"
        c.get_subject().CN = engine_id
        c.set_serial_number(1000)
        c.gmtime_adj_notBefore(0)
        c.gmtime_adj_notAfter(10*365*24*60*60)
        c.set_issuer(c.get_subject())
        c.set_pubkey(k)
        c.sign(k, 'sha1')

        try:
            open(cf, 'w').write(
                crypto.dump_certificate(crypto.FILETYPE_PEM, c))
            open(kf, 'w').write(
                crypto.dump_privatekey(crypto.FILETYPE_PEM, k))
        except Exception, ex:
            print "[e] failed to create local key file: %s" % str(ex)
            return False

        return True

    # -------------------------------------------------------------------------
    #
    # -------------------------------------------------------------------------

    def create_local_certificates(self):
        cf = self.config.get('root') + "/config/certificates/" +\
             self.config.get('data').get('security').get('ssl').get('certificate_file')

        kf = self.config.get('root') + "/config/certificates/" +\
             self.config.get('data').get('security').get('ssl').get('key_file')

        eid = self.config.get('data').get('security').get('ssl').get('certificate_file')
        eid = eid.split(".")[0]
        return self.create_certificate(eid, cf, kf)

    # -------------------------------------------------------------------------
    #
    # -------------------------------------------------------------------------

    def enable_engine_ssl(self, engine_id):
        try:
            engine = self.config.get('data').get('engines').get(engine_id)
            self.config.get('data').get('engines').get(engine_id)['ssl'] = 1
            self.config.save()
        except Exception, ex:
            print "[e] failed to enable SSL for engine '%s'" % engine_id
            return False
        return True

    # -------------------------------------------------------------------------
    #
    # -------------------------------------------------------------------------

    def do_ssl(self, args):
        args = args.split(" ")
        if len(args) != 2:
            print "[e] syntax error"
            return

        engine = self.get_engine_by_id(args[1])
        if not engine: return

        uri = None
        if args[0] == "enable":
            # Make sure we got our local cert and key
            if not self.check_local_certificates():
                if not self.create_local_certificates():
                    print "[e] failed to create certificates"
                    return
            # Not sure if I want to have CA cert and sign each cert with 
            # that. Probably would make things simpler, but... will see.
            cert_root = self.config.get('root') + "/config/certificates/"
            ccf = cert_root + self.config.get('data').get('security').get('ssl').get('certificate_file')

            try:
                client = Utils.read_file(ccf)
            except Exception, ex:
                print "[e] failed to read certificates: %s" % str(ex)
                return

            # read in certs, base64 and include
            r_object_data = {
                "client": base64.b64encode(client),
                "id": args[1]
            }

            r_object = {
                "method": "POST",
                "uri": "/setup/ssl?enable=1&apikey=" + engine.get('apikey'),
                "data": r_object_data
            }

            rc = Utils.engine_request(self.config,
                                     engine.get('address'),
                                     engine.get('port'),
                                     r_object,
                                     args[1])
            if not rc:
                print "[e] certificate distribution failed"
                return
            sc = rc.get('status')
            if sc != 200:
                print "[e] certificate distribution failed: %s" % rc.get('data').get('message')
                return

            engine_cert = rc.get('data').get('certificate')
            if not engine_cert:
                print "[e] certificate distribution failed: no certificate received from engine"
                return

            try:
                engine_cert = base64.b64decode(engine_cert)
            except Exception, ex:
                print "[e] invalid engine certificate received: %s" % str(ex)
                return

            try:
                Utils.save_file(cert_root + args[1] + ".crt", engine_cert, False)
            except Exception, ex:
                print "[e] failed to save engine certificate: %s" % str(ex)
                return

            self.enable_engine_ssl(args[1])

        elif args[0] == "disable":
            r_object = {
                "method": "POST",
                "uri": "/setup/ssl?enable=0&apikey=" + engine.get('apikey'),
                "data": None
            }

            rc = Utils.engine_request(self.config,
                                     engine.get('address'),
                                     engine.get('port'),
                                     r_object,
                                     args[1])
            if not rc:
                print "[e] failed to disable SSL on engine '%s'" % args[1]
                return
            sc = rc.get('status')
            if sc != 200:
                print "[e] failed to disable SSL on engine '%s': %s" %\
                      (args[1], rc.get('data').get('message'))
                return

            self.config.get('data').get('engines').get(args[1])['ssl'] = 0
            self.config.save()
        else:
            print "[e] invalid option '%s'" % args[0]
            return

    # -------------------------------------------------------------------------
    #
    # -------------------------------------------------------------------------

    def help_ssl(self):
        print "\nEnable or disable SSL for a given engine connection.\n\n" +\
              "Syntax: ssl [ enable | disable ] <engine id>\n"

    # -------------------------------------------------------------------------
    #
    # -------------------------------------------------------------------------

    def do_acl(self, args):
        engine_id = None
        command   = None
        address   = None
        args = args.split(" ")
        if args < 2:
            print "[e] syntax error"
            self.help_acl()
            return

        try:
            engine_id = args[0]
            command   = args[1]
            if command in ["add", "remove"]:
                address = args[2]
        except Exception, ex:
            print "[e] syntax error"
            self.help_acl()
            return

        engine = self.get_engine_by_id(engine_id)
        if not engine: return

        if command == "list":
            r_object = {
                "method": "GET",
                "uri": "/management/acl/list?apikey=" + engine.get('apikey'),
                "data": None
            }

            rc = Utils.engine_request(self.config,
                                      engine.get('address'),
                                      engine.get('port'),
                                      r_object,
                                      engine_id)
            if not rc:
                print "[e] failed to retrieve ACL"
                return
            if rc.get('status') != 200:
                print "[e] failed to retrieve ACL: %s" % rc.get('data').get('message')
                return

            allowed_list = rc.get('data').get('message')
            if len(allowed_list) == 0:
                print "ACL empty for engine '%s'" % engine_id
                return

            print
            print "%-15s\t%s" % ("Client", "Certificate")
            print "-" * 80
            for allowed in allowed_list:
                cp = allowed.get('certificate')
                if not cp:
                    cp = "Not set"
                else:
                    cp = "/config/" + "".join(cp.split("config/")[1])
                print "%-15s\t%s" % (allowed.get('address'), cp)
            print
        elif command == "add":
            r_object = {
                "method": "POST",
                "uri": "/management/acl/add?apikey=" + engine.get('apikey'),
                "data": {"address": address}
            }

            rc = Utils.engine_request(self.config,
                                      engine.get('address'),
                                      engine.get('port'),
                                      r_object,
                                      engine_id)
            if not rc:
                print "[e] failed to update ACL"
                return
            if rc.get('status') != 200:
                print "[e] failed to update ACL: %s" % rc.get('data').get('message')
                return
        elif command == "remove":
            r_object = {
                "method": "POST",
                "uri": "/management/acl/remove?apikey=" + engine.get('apikey'),
                "data": {"address": address}
            }

            rc = Utils.engine_request(self.config,
                                      engine.get('address'),
                                      engine.get('port'),
                                      r_object,
                                      engine_id)
            if not rc:
                print "[e] failed to update ACL"
                return
            if rc.get('status') != 200:
                print "[e] failed to update ACL: %s" % rc.get('data').get('message')
                return
        else:
            print "[e] invalid action requested"
            return

    # -------------------------------------------------------------------------
    #
    # -------------------------------------------------------------------------

    def help_acl(self):
        print "\nModify the ACL of an engine.\n\n" +\
              "Syntax: acl <engine ID> [ list | add <IP address> | remove <IP address> ]\n"


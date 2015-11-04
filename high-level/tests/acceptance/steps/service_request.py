""" Lettuce implementation for the service_request.feature. """
import lettuce
import urllib
import os.path
import json
import ast
import subprocess
from sspl_hl.providers.service_manager.provider import ServiceManagerProvider
from sspl_hl.providers.node.provider import NodeProvider
from sspl_hl.providers.fru.provider import FRUProvider


# Note:  We should use the plex registry to programatically generate this URL
# to protect against changes in how plex surfaces apps/providers/etc.  But
# since this is test code, we won't worry about it.
SERVICE_URI = \
    "http://localhost:8080/apps/sspl_hl/providers/service_manager/data"
NODE_URI = "http://localhost:8080/apps/sspl_hl/providers/node/data"
HA_URI = "http://localhost:8080/apps/sspl_hl/providers/ha/data"
FRU_URI = "http://localhost:8080/apps/sspl_hl/providers/fru/data"


@lettuce.step(u'When I request "([^"]*)" service "([^"]*)" for all nodes')
def service_cmd_for_all_nodes(_, service, cmd):
    """ Request given service take given action by hitting data provider url.
    """
    url = SERVICE_URI + "?serviceName={service}&command={cmd}".format(
        service=service, cmd=cmd
        )
    urllib.urlopen(url=url)


@lettuce.step(u'When I request "([^"]*)" node "([^"]*)" for all nodes')
def node_cmd_for_all_nodes(_, node, cmd):
    """ Request given node take given action by hitting data provider url.
    """
    url = NODE_URI + "?target={node}&command={cmd}".format(
        node=node, cmd=cmd
        )
    urllib.urlopen(url=url).read()


@lettuce.step(u'When I make Ha request "([^"]*)" and "([^"]*)" for all nodes')
def ha_cmd_for_all_nodes(_, cmd, subcmd):
    """ Execute ha request by hitting ha data provider url.
    """
    url = HA_URI + "?command={cmd}&subcommand={subcmd}".format(
        cmd=cmd, subcmd=subcmd
        )
    urllib.urlopen(url=url).read()


@lettuce.step(u'When I run "([^"]*)"')
def when_i_run(_, cli_command):
    """ Run a CLI command.  """
    proc = subprocess.Popen(
        cli_command.split(),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        )
    output, err = proc.communicate()  # pylint: disable=unused-variable
    lettuce.world.response = output
    lettuce.world.exitcode = proc.returncode


@lettuce.step(u'Then a serviceRequest message to "([^"]*)" "([^"]*)" is sent')
def servicerequest_msg_sent(_, command, service_name):
    """ Ensure proper message generated and enqueued. """
    # wait for a message to appear in the fake_halond output directory
    lettuce.world.wait_for_condition(
        status_func=lambda: len(os.listdir('/tmp/fake_halond')) > 0,
        max_wait=5,
        timeout_message="Timeout expired while waiting for message to arrive "
        "in fake_halond output directory."
        )

    first_file = sorted(
        os.listdir('/tmp/fake_halond'),
        key=lambda f: os.stat(os.path.join('/tmp/fake_halond', f)).st_mtime
        )[0]
    contents = open(os.path.join('/tmp/fake_halond', first_file), 'r').read()

    # pylint: disable=protected-access
    exp = json.dumps(ServiceManagerProvider._generate_service_request_msg(
        service_name=service_name, command=command
        ))
    # pylint: enable=protected-access

    # alter the 'time' and 'messageId' field to match.  (We expect a minor
    # variation).
    tmp = json.loads(exp)
    tmp['time'] = json.loads(contents)['time']
    tmp['message']['messageId'] = json.loads(contents)['message']['messageId']
    exp = json.dumps(tmp)

    assert json.loads(contents) == json.loads(exp), \
        "Message doesn't match.  Expected '{expected}' but got '{actual}'" \
        .format(expected=exp, actual=contents)

    os.unlink(os.path.join('/tmp/fake_halond', first_file))


@lettuce.step(
    u'Then a nodeRequest message to "([^"]*)" --node_spec "([^"]*)" is sent'
)
def noderequest_msg_sent(_, command, target):
    """ Ensure proper message is generated for a specific
    node and enqueued. """
    _noderequest_msg_sent(command, target)


@lettuce.step(u'Then a nodeRequest message to "([^"]*)" is sent')
def all_noderequest_msg_sent(_, command):
    """ Ensure proper message is generated for all node and enqueued. """
    _noderequest_msg_sent(command)


@lettuce.step(u'Then a command request to ha with "([^"]*)" "([^"]*)" is sent')
def hacmdrequest_sent(_, command, subcommand):
    """ Ensure proper message generated and enqueued. """
    contents = lettuce.world.response

    # Tests that response contains valid data.
    # Valid response would contain data in the sample format as below:
    # \n12434567 [label=\"Service ServiceName {snString = 'HA.EQTracker'}\"]
    # \nn812340088 [label=\"MonitorConf (Processes [MonitoredSerialized ])\"]

    assert 'label' in contents, \
        "Command: ha {cmd} {subcmd} Message doesn't match. \
        Expected response data but got '{actual}'" \
        .format(cmd=command, subcmd=subcommand, actual=contents)


def validate_admin_output(contents, cmd, username):
    ''' Method to validate cstor admin output '''
    # pylint: disable=too-many-locals
    out = ast.literal_eval(contents)
    ugroup1 = 'Test'
    ug1 = ['sheldon', 'victor']
    ugroup2 = 'Cstor'
    ug2 = ['howard', 'leonard']

    for allusers in out:
        for user in allusers:
            userstr = user[0]
            userdet = user[1]
            udparts = userstr.split(',')
            usercn = udparts[0].split('=')[1]

            if usercn == 'Manager':
                continue
            userou = udparts[1].split('=')[1]
            userdc1 = udparts[2].split('=')[1]
            userdc2 = udparts[3].split('=')[1]

            assert userdc1 == 'seagate' and userdc2 == 'com', \
                "dc value for LDAP users doesnt match. \
                Expected: response dc='{exp1}' and dc='{exp2}'' \
                but got dc='{act1}' and dc='{act2}'" \
                .format(exp1='seagate', exp2='com', act1=userdc1, act2=userdc2)

            if usercn in ug1:
                assert usercn in ug1 and userou == ugroup1, \
                    "User values for LDAP users doesnt match. \
                    Expected: response cn='{exp1}' and ou='{exp2}' \
                    but got cn='{act1}' and ou='{act2}'" \
                    .format(exp1=ug1, exp2=ugroup1, act1=usercn, act2=userou)

            if usercn in ug2:
                assert usercn in ug2 and userou == ugroup2, \
                    "User values for LDAP users doesnt match. \
                    Expected: response cn='{exp1}' and ou='{exp2}' \
                    but got cn='{act1}' and ou='{act2}'" \
                    .format(exp1=ug2, exp2=ugroup2, act1=usercn, act2=userou)

            if cmd == 'show':
                usercn = userdet["cn"][0]
                (ucn, uou) = username.split('@')
                assert usercn == ucn and userou == uou, \
                    "User values for LDAP users doesnt match. \
                    Expected: response cn='{exp1}' and ou='{exp2}' \
                    but got cn='{act1}' and ou='{act2}'" \
                    .format(exp1=usercn, exp2=userou, act1=ucn, act2=uou)


@lettuce.step(u'Then a command list request to admin \
with "([^"]*)" "([^"]*)" is sent')
def adminlistcmdrequest_sent(_, command, subcommand):
    """ Ensure proper message generated and enqueued. """
    contents = lettuce.world.response
    assert 'objectClass' in contents, \
        "Command: admin {cmd} {subcmd} Message doesn't match. \
        Expected response data with LDAP users list but got '{actual}'" \
        .format(cmd=command, subcmd=subcommand, actual=contents)
    validate_admin_output(contents, 'list', 'all')


@lettuce.step(u'Then a command show request to admin \
with "([^"]*)" "([^"]*)" "([^"]*)" is sent')
def adminshowcmdrequest_sent(_, command, subcommand, user):
    """ Ensure proper message generated and enqueued. """
    contents = lettuce.world.response
    assert 'objectClass' in contents, \
        "Command: admin {cmd} {subcmd} {user} Message doesn't match. \
        Expected response data but got '{actual}'" \
        .format(cmd=command, subcmd=subcommand, user=user, actual=contents)
    validate_admin_output(contents, 'show', user)


def _wait_for_halon():
    """
    Waits for a fake_halond to output dump into
    a directory
    @return: Contents of fake_halond file and filename
    @rtype: tuple
    @raise: OSError, IOError
    """
    lettuce.world.wait_for_condition(
        status_func=lambda: len(os.listdir('/tmp/fake_halond')) > 0,
        max_wait=5,
        timeout_message="Timeout expired while waiting for message to arrive "
                        "in fake_halond output directory."
    )
    try:
        first_file = sorted(
            os.listdir('/tmp/fake_halond'),
            key=lambda f: os.stat(os.path.join('/tmp/fake_halond', f)).st_mtime
        )[0]
        contents = open(
            os.path.join('/tmp/fake_halond', first_file),
            'r').read()
    except OSError:
        raise OSError("Unable to list fake_halond")
    except IOError:
        raise IOError("Unable to read fake_halond output file")
    return contents, first_file


@lettuce.step(u'Then a fruRequest message to "([^"]*)" "([^"]*)" is sent')
def fru_request_msg_sent(_, command, hwtype):
    """ Ensure proper message generated and enqueued. """
    # wait for a message to appear in the fake_halond output directory
    contents, first_file = _wait_for_halon()

    # pylint: disable=protected-access
    exp = json.dumps(FRUProvider._generate_fru_request_msg(
        fru_target=hwtype, fru_command=command
        ))
    # pylint: enable=protected-access

    tmp = json.loads(exp)
    tmp['time'] = json.loads(contents)['time']
    tmp['message']['messageId'] = json.loads(contents)['message']['messageId']
    exp = json.dumps(tmp)

    assert json.loads(contents) == json.loads(exp), \
        "Message doesn't match.  Expected '{expected}' but got '{actual}'" \
        .format(expected=exp, actual=contents)

    os.unlink(os.path.join('/tmp/fake_halond', first_file))


@lettuce.step(u'the exit code is "([^"]*)"')
def exit_code_is_x(_, exitcode):
    """ Ensure expected exit code for previously run shell command.

    It's expected that 'When I run '<cmd>' has been previously called.
    """
    assert lettuce.world.exitcode == int(exitcode), \
        "Error: exit code mismatch.  Expected {expected} but got {actual}" \
        .format(
            expected=exitcode,
            actual=lettuce.world.exitcode
        )


def _noderequest_msg_sent(command, target=None):
    """ Ensure proper message is generated and enqueued. """
    # wait for a message to appear in the fake_halond output directory
    lettuce.world.wait_for_condition(
        status_func=lambda: len(os.listdir('/tmp/fake_halond')) > 0,
        max_wait=5,
        timeout_message="Timeout expired while waiting for message to arrive "
        "in fake_halond output directory."
        )
    first_file = sorted(
        os.listdir('/tmp/fake_halond'),
        key=lambda f: os.stat(os.path.join('/tmp/fake_halond', f)).st_mtime
        )[0]
    contents = open(os.path.join('/tmp/fake_halond', first_file), 'r').read()

    # pylint: disable=protected-access
    exp = json.dumps(NodeProvider._generate_node_request_msg(
        target=target, command=command
        ))
    # pylint: enable=protected-access

    tmp = json.loads(exp)
    tmp['time'] = json.loads(contents)['time']
    tmp['message']['messageId'] = json.loads(contents)['message']['messageId']
    exp = json.dumps(tmp)

    assert json.loads(contents) == json.loads(exp), \
        "Message doesn't match.  Expected '{expected}' but got '{actual}'" \
        .format(expected=exp, actual=contents)

    os.unlink(os.path.join('/tmp/fake_halond', first_file))

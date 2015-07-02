# vCloud Air CLI 0.1
#
# Copyright (c) 2014 VMware, Inc. All Rights Reserved.
#
# This product is licensed to you under the
# Apache License, Version 2.0 (the "License").
# You may not use this product except in compliance with the License.
#
# This product may include a number of subcomponents with
# separate copyright notices and license terms. Your use of the source
# code for the these subcomponents is subject to the terms and
# conditions of the subcomponent's license, as noted in the LICENSE file.
#


import os
import operator
import click
import pkg_resources
import requests
from cmd_proc import CmdProc
from vca_cli_utils import VcaCliUtils
from pyvcloud.vcloudair import VCA


CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])
default_operation = 'list'
utils = VcaCliUtils()


@click.group(context_settings=CONTEXT_SETTINGS, invoke_without_command=True)
@click.option('-p', '--profile', default=None,
              metavar='<profile>', help='Profile id')
@click.option('-f', '--profile-file', default='~/.vcarc',
              metavar='<file>', help='Profile file', type=click.Path())
@click.option('-v', '--version', is_flag=True, help='Show version')
@click.option('-d', '--debug', is_flag=True, help='Enable debug')
@click.option('-j', '--json', 'json_output',
              is_flag=True, help='Results as JSON object')
@click.option('-x', '--xml', 'xml_output',
              is_flag=True, help='Results as XML document')
@click.option('-i', '--insecure', is_flag=True,
              help='Perform insecure SSL connections')
@click.pass_context
def cli(ctx=None, profile=None, profile_file=None, version=None, debug=None,
        json_output=None, xml_output=None, insecure=None):
    """VMware vCloud Air Command Line Interface."""
    if version:
        version_vca_cli = pkg_resources.require("vca-cli")[0].version
        version_pyvcloud = pkg_resources.require("pyvcloud")[0].version
        msg = 'vca-cli version %s (pyvcloud: %s)' % \
              (version_vca_cli, version_pyvcloud)
        click.secho(msg, fg='blue')
        return
    if ctx.invoked_subcommand is None:
        help_text = ctx.get_help()
        print(help_text)
        return
    if insecure:
        utils.print_warning('InsecureRequestWarning: ' +
                            'Unverified HTTPS request is being made. ' +
                            'Adding certificate verification is strongly ' +
                            'advised.')
        requests.packages.urllib3.disable_warnings()
    profile_file_fq = os.path.expanduser(profile_file)
    ctx.obj = CmdProc(profile=profile, profile_file=profile_file_fq,
                      json_output=json_output, xml_output=xml_output,
                      debug=debug, insecure=insecure)
    ctx.obj.load_config(profile, profile_file)


@cli.command()
@click.pass_obj
def status(cmd_proc):
    """Show current status"""
    cmd_proc.save_current_config()
    result = cmd_proc.re_login()
    if not result:
        utils.print_error('Not logged in', cmd_proc)
    headers = ['Key', 'Value']
    table = []
    table.append(['vca_cli_version',
                 pkg_resources.require("vca-cli")[0].version])
    table.append(['pyvcloud_version',
                 pkg_resources.require("pyvcloud")[0].version])
    table.append(['profile_file', cmd_proc.profile_file])
    table.append(['profile', cmd_proc.profile])
    table.append(['host', cmd_proc.vca.host])
    table.append(['user', cmd_proc.vca.username])
    table.append(['instance', cmd_proc.instance])
    table.append(['org', cmd_proc.vca.org])
    if cmd_proc.password is None or len(cmd_proc.password) == 0:
        table.append(['password', str(cmd_proc.password)])
    else:
        table.append(['password', '<encrypted>'])
    if cmd_proc.vca is not None:
        table.append(['type', cmd_proc.vca.service_type])
        table.append(['version', cmd_proc.vca.version])
        if cmd_proc.vca.vcloud_session is not None:
            table.append(['org_url', cmd_proc.vca.vcloud_session.url])
    table.append(['active session', str(result)])
    utils.print_table('Status:', headers, table, cmd_proc)


@cli.command()
@click.pass_obj
def profile(cmd_proc):
    """Show profiles"""
    cmd_proc.save_current_config()
    cmd_proc.print_profile_file()


#  TODO: login to a VDC
@cli.command()
@click.pass_obj
@click.argument('user')
@click.option('-p', '--password', prompt=True, metavar='<password>',
              confirmation_prompt=False, hide_input=True, help='Password')
@click.option('-d', '--do-not-save-password', is_flag=True,
              default=False, help='Do not save password')
@click.option('-v', '--version', 'service_version',
              default='5.7', metavar='[5.5 | 5.6 | 5.7]',
              type=click.Choice(['5.5', '5.6', '5.7']), help='')
@click.option('-H', '--host', default='https://vca.vmware.com',
              metavar='<host>',
              help='')
@click.option('-i', '--instance', default=None, metavar='<instance>',
              help='Instance Id')
@click.option('-o', '--org', default=None, metavar='<organization>',
              help='Organization Name')
@click.option('-c', '--host-score', 'host_score',
              metavar='<host>',
              default='https://score.vca.io', help='URL of the Score server')
def login(cmd_proc, user, host, password, do_not_save_password,
          service_version, instance, org, host_score):
    """Login to a vCloud service"""
    if not (host.startswith('https://') or host.startswith('http://')):
        host = 'https://' + host
    if not (host_score.startswith('https://') or
            host_score.startswith('http://')):
        host_score = 'https://' + host_score
    try:
        cmd_proc.logout()
        result = cmd_proc.login(host, user, password,
                                instance=instance,
                                org=org,
                                version=service_version,
                                save_password=(not do_not_save_password))
        if result:
            utils.print_message("User '%s' logged in, profile '%s'" %
                                (cmd_proc.vca.username, cmd_proc.profile),
                                cmd_proc)
            if not do_not_save_password:
                utils.print_warning('Password encrypted and saved ' +
                                    'in local profile. Use ' +
                                    '--do-not-save-password to disable it.',
                                    cmd_proc)
            if cmd_proc.vca.service_type in [VCA.VCA_SERVICE_TYPE_VCA]:
                if instance is not None:
                    result = _use_instance(cmd_proc, instance)
                    if result:
                        cmd_proc.save_current_config()
            elif cmd_proc.vca.service_type in [VCA.VCA_SERVICE_TYPE_VCHS]:
                if instance is not None or org is not None:
                    result = _use_instance_org(cmd_proc, instance, org)
                    if result:
                        cmd_proc.save_current_config()
        else:
            utils.print_error('Can\'t login', cmd_proc)
    except Exception as e:
        utils.print_error('Can\'t login: ' + str(e), cmd_proc)


@cli.command()
@click.pass_obj
def logout(cmd_proc):
    """Logout from a vCloud service"""
    user = cmd_proc.vca.username
    profile = cmd_proc.profile
    cmd_proc.logout()
    utils.print_message("User '%s' logged out, profile '%s'" %
                        (user, profile),
                        cmd_proc)
# TODO: DELETE https://vchs.vmware.com/api/vchs/session


#  TODO: select first VDC
def _use_instance(cmd_proc, instance):
    result = cmd_proc.vca.login_to_instance_sso(instance)
    if result:
        cmd_proc.instance = instance
# TODO: check instance->plan->serviceName == com.vmware.vchs.compute
# TODO: is this needed?
        cmd_proc.vca.org = cmd_proc.vca.vcloud_session.organization.\
            get_name()
        utils.print_message("Using instance:org '%s':'%s'"
                            ", profile '%s'" %
                            (instance, cmd_proc.vca.org, cmd_proc.profile),
                            cmd_proc)
    else:
        utils.print_error("Unable to select instance '%s'"
                          ", profile '%s'" %
                          (instance, cmd_proc.profile),
                          cmd_proc)
    return result


#  TODO: select first VDC
def _use_instance_org(cmd_proc, instance, org):
    if instance is None or '' == instance:
        utils.print_message('Please provide a valid instance '
                            "with the '--instance' param")
        utils.print_message("Use 'vca instance' "
                            "for a list of instances")
        return False
    if org is None or '' == org:
        utils.print_message('Please provide a valid organization '
                            "with the '--org' param")
        utils.print_message("Use 'vca instance info --instance %s' "
                            "for a list of organizations" % instance)
        return False
    result = cmd_proc.vca.login_to_org(instance, org)
    if result:
        cmd_proc.instance = instance
        utils.print_message("Using instance:org '%s':'%s'"
                            ", profile '%s'" %
                            (instance, cmd_proc.vca.org, cmd_proc.profile),
                            cmd_proc)
    else:
        utils.print_error("Unable to select instance:org '%s':'%s'"
                          ", profile '%s'" %
                          (instance, org, cmd_proc.profile),
                          cmd_proc)
    return result


def _list_orgs_in_instance(cmd_proc, instance):
    message = "Available orgs in instance '%s'"\
              ", profile '%s':" %\
              (instance, cmd_proc.profile)
    headers = ["Instance Id", "Org", "Status", "Selected"]
    table = []
    for vdc in cmd_proc.vca.get_vdc_references(instance):
        selected = '*' if cmd_proc.vca.org == vdc.name else ' '
        table.append([instance, vdc.name, vdc.status, selected])
    utils.print_table(message, headers, table,
                      cmd_proc)


@cli.command()
@click.pass_obj
@click.argument('operation', default=default_operation,
                metavar='[list | info | use]',
                type=click.Choice(['list', 'info', 'use']))
@click.option('-i', '--instance', default='', metavar='<instance>',
              help='Instance Id')
@click.option('-o', '--org', default='', metavar='<organization>',
              help='Organization Id')
def instance(cmd_proc, operation, instance, org):
    """Operations with Instances"""
    if cmd_proc.vca.service_type not in \
       [VCA.VCA_SERVICE_TYPE_VCA, VCA.VCA_SERVICE_TYPE_VCHS]:
        utils.print_message('This service type doesn\'t support this command')
        return
    result = cmd_proc.re_login()
    if not result:
        utils.print_error('Not logged in', cmd_proc)
        return
    if 'list' == operation:
        headers = []
        table = []
        if cmd_proc.vca.service_type == VCA.VCA_SERVICE_TYPE_VCA:
            headers = ['Service Group', 'Region', 'Plan', 'Instance Id',
                       'Selected']
            instances = cmd_proc.vca.instances
            plans = cmd_proc.vca.get_plans()
            service_groups = cmd_proc.vca.get_service_groups()
            items = instances if instances else []
            for item in items:
                plan_name = filter(lambda plan: plan['id'] == item['planId'],
                                   plans)[0]['name']
                service_group = filter(lambda sg:
                                       sg['id'] == item['serviceGroupId'],
                                       service_groups['serviceGroup'])
                service_group_name = '' if len(service_group) == 0 else \
                                     service_group[0]['displayName']
                selected = '*' if cmd_proc.instance == item['id'] else ' '
                table.append([
                    service_group_name,
                    item['region'].split('.')[0],
                    plan_name,
                    item['id'],
                    selected
                ])
        elif cmd_proc.vca.service_type == VCA.VCA_SERVICE_TYPE_VCHS:
            headers = ['Service Group', 'Region', 'Plan', 'Instance Id',
                       'Selected', 'Type']
            table = []
            for s in cmd_proc.vca.services.get_Service():
                selected = '*' if cmd_proc.instance == s.serviceId else ' '
                table.append(['', s.region, '', s.serviceId, selected,
                             s.serviceType])
        sorted_table = sorted(table, key=operator.itemgetter(0), reverse=False)
        utils.print_table("Available instances for user '%s'"
                          ", profile '%s':" %
                          (cmd_proc.vca.username, cmd_proc.profile),
                          headers, sorted_table, cmd_proc)
    elif 'info' == operation:
        if '' == instance:
            instance = cmd_proc.instance
        if cmd_proc.vca.service_type == VCA.VCA_SERVICE_TYPE_VCA:
            instance_data = cmd_proc.vca.get_instance(instance)
            plan = cmd_proc.vca.get_plan(instance_data['planId'])
            if cmd_proc.json_output:
                json_object = {'instance': instance_data, 'plan': plan}
                utils.print_json(json_object, 'Instance and Plan details',
                                 cmd_proc)
            else:
                utils.print_json(instance_data, 'Instance details:', cmd_proc)
                utils.print_json(plan, 'Plan details:', cmd_proc)
        elif cmd_proc.vca.service_type == VCA.VCA_SERVICE_TYPE_VCHS:
            _list_orgs_in_instance(cmd_proc, instance)
    elif 'use' == operation:
        if cmd_proc.vca.service_type == VCA.VCA_SERVICE_TYPE_VCA:
            _use_instance(cmd_proc, instance)
        elif cmd_proc.vca.service_type == VCA.VCA_SERVICE_TYPE_VCHS:
            _use_instance_org(cmd_proc, instance, org)
    else:
        utils.print_message('Not implemented')
    cmd_proc.save_current_config()


@cli.command()
@click.pass_obj
@click.argument('operation', default=default_operation,
                metavar='[list | info | use]',
                type=click.Choice(['list', 'info', 'use']))
@click.option('-i', '--instance', default='', metavar='<instance>',
              help='Instance Id')
@click.option('-o', '--org', default='', metavar='<organization>',
              help='Organization Id')
def org(cmd_proc, operation, instance, org):
    """Operations with Organizations"""
    result = cmd_proc.re_login()
    if not result:
        utils.print_error('Not logged in', cmd_proc)
        return
    if 'list' == operation:
        if cmd_proc.vca.service_type == VCA.VCA_SERVICE_TYPE_VCHS:
            if '' == instance:
                instance = cmd_proc.instance
            _list_orgs_in_instance(cmd_proc, instance)
            return
        headers = ['Org', 'Selected']
        table = []
        if cmd_proc.vca is not None and\
           cmd_proc.vca.vcloud_session is not None:
            table.append([cmd_proc.vca.vcloud_session.organization.get_name(),
                         '*'])
        sorted_table = sorted(table, key=operator.itemgetter(0), reverse=False)
        utils.print_table("Available orgs in instance '%s'"
                          ", profile '%s':" %
                          (cmd_proc.instance, cmd_proc.profile),
                          headers, sorted_table,
                          cmd_proc)
    elif 'info' == operation:
        if '' == org:
            org = cmd_proc.vca.org
        if cmd_proc.vca is not None and \
           cmd_proc.vca.vcloud_session is not None and \
           cmd_proc.vca.vcloud_session.organization is not None and \
           cmd_proc.vca.vcloud_session.organization.get_name() == org:
            table = cmd_proc.org_to_table(cmd_proc.vca)
            headers = ["Type", "Name"]
            utils.print_table(
                "Details for instance:org '%s':'%s', profile '%s':" %
                (cmd_proc.instance, org, cmd_proc.profile),
                headers, table, cmd_proc)
        else:
            utils.print_error("Org not found '%s'" % org)
    elif 'use' == operation:
        if cmd_proc.vca.service_type == VCA.VCA_SERVICE_TYPE_VCA:
            utils.print_message('Operation not supported in '
                                'this service type. '
                                "Use 'instance' command to change "
                                'instances')
        elif cmd_proc.vca.service_type == VCA.VCA_SERVICE_TYPE_VCHS:
            result = _use_instance_org(cmd_proc, instance, org)
        elif cmd_proc.vca.service_type == VCA.VCA_SERVICE_TYPE_STANDALONE:
            utils.print_message('Operation not supported in '
                                'this service type. '
                                "Use the '--org' param in the login command"
                                'to select another organization')
        else:
            utils.print_message('Operation not supported '
                                'in this service type')
    cmd_proc.save_current_config()


if __name__ == '__main__':
    pass
else:
    import vca_cli_vca  # NOQA
    import vca_cli_compute  # NOQA
    import vca_cli_network  # NOQA
    import vca_cli_bp  # NOQA
    import vca_cli_sql  # NOQA
    import vca_cli_example  # NOQA

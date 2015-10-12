"""Salt states to manage Jenkins configuration."""

import difflib
import logging
import os

from lxml import etree


log = logging.getLogger(__name__)


def _xmlpp(tree):
    return etree.tostring(tree, pretty_print=True)


def _changes_diff(before, after):
    return difflib.unified_diff(before.splitlines(), after.splitlines())


def _find_or_add(tagname, parent):
    tag = parent.find(tagname)
    if tag is None:
        tag = etree.SubElement(parent, tagname)
    return tag


def _subelement_with_text(parent, tagname, text):
    tag = etree.SubElement(parent, tagname)
    tag.text = str(text)
    return tag


def _root_tag(tagname):
    def decorator(func):
        @wraps(func)
        def wrapper(tree, *args, **kwargs):
            root = tree.getroot()
            if root.tag != tagname:
                raise ValueError(
                    'root element is not the <{0}> tag'.format(tagname))
            return func(tree, *args, **kwargs)
        return wrapper
    return decorator


def _get_config(fname):
    """Return file path corresponding to `fname` configuration file.

    Raise IOError if file does not exist.
    """
    jenkins_home = __salt__['pillar.get']('jenkins.home')
    fpath = os.path.join(jenkins_home, fname)
    if not os.path.isfile(fpath):
        raise IOError('{0} not found in jenkins home directory {1}'.format(
            fname, jenkins_home))
    return fpath


def _parse_config(fname):
    """Return XML tree parsed from `fname` configuration file.
    """
    fpath = _get_config(fname)
    parser = etree.XMLParser(remove_blank_text=True)
    return etree.parse(fpath, parser=parser)


def _write_config(fname, tree):
    """Write XML `tree` to `fname` configuration file.
    """
    fpath = _get_config(fname)
    log.info('writting updated Jenkins configuration to {0}', fpath)
    tree.write(fpath,
               pretty_print=True,
               xml_declaration=True,
               encoding='UTF-8')


@_root_tag('hudson')
def _insert_docker(tree, name, version, server_url, connect_timeout,
                   read_timeout, capacity):
    hudson = tree.getroot()
    clouds = _find_or_add('clouds', hudson)
    dockercloud_tag = 'com.nirima.jenkins.plugins.docker.DockerCloud'
    for dockercloud in clouds.findall(dockercloud_tag):
        nametag = dockercloud.find('name')
        if nametag is not None and nametag.text == 'name':
            break
    else:
        dockercloud = etree.SubElement(
            clouds, dockercloud_tag,
            attrib={'plugin': 'docker-plugin@' + version})
    _subelement_with_text(
        dockercloud, 'name', name)
    etree.SubElement(dockercloud, 'templates',
                     attrib={'class': 'empty-list'})
    _subelement_with_text(dockercloud, 'serverUrl', server_url)
    _subelement_with_text(dockercloud, 'connectTimeout', connect_timeout)
    _subelement_with_text(dockercloud, 'readTimeout', read_timeout)
    etree.SubElement(dockercloud, 'credentialsId')
    _subelement_with_text(dockercloud, 'containerCap', capacity)


def _empty_result(name):
    return {
        'changes': {},
        'comment': '',
        'name': name,
        'result': None,
    }


def _error(ret, msg):
    ret['comment'] = msg
    ret['result'] = False
    return ret


def _config_xmltree(func):
    """Decorator that ensures the configuration file specified in `conffile`
    parameter of underlying function is available and set the `_tree` keyword
    argument of underlying function if so.
    """
    @wraps(func)
    def wrapper(name, *args, **kwargs):
        fname = kwargs['conffile']
        ret = _empty_result(name)
        try:
            tree = _parse_config(fname)
        except Exception:
            def error_func(name, *args, **kwargs):
                log.exception()
                msg = 'failed to parse configuration file {0}'.format(
                    conffile)
                return _error(ret, msg)
            return error_func
        kwargs['_tree'] = tree
        return func(name, *args, **kwargs)
    return wrapper


@_config_xmltree
def dockercloud(name, server_url, connect_timeout=0, read_timeout=0,
                capacity=100, conffile='config.xml', _tree=None):
    """Add a new Docker cloud to Jenkins configuration.

    .. code-block:: yaml

        my_docker:
          jenkins_config.dockercloud:
            - server_url: http://my.docker.server:9876

    """
    version = '0.15.0'  # TODO get this from python-jenkins call
    ret = _empty_result(name)
    before = etree.tostring(_tree, pretty_print=True)
    _insert_docker(_tree, name, version, server_url, connect_timeout,
                   read_timeout, capacity)
    after = etree.tostring(_tree, pretty_print=True)
    changes = _changes_diff(before, after)
    comment = 'updated configuration file {0}'.format(conffile)
    if __opts__['test']:
        ret['comment'] = '\n'.join(['would ' + comment, 'diff', changes])
        ret['result'] = None
        return ret
    _write_config(tree, conffile)
    ret['comment'] = '\n'.join([comment, 'diff', changes])
    ret['result'] = True
    return ret


@_root_tag('jenkins.model.JenkinsLocationConfiguration')
def _set_admin_email(tree, emailaddress):
    root = tree.getroot()
    email = _find_or_add('adminAddress', root)
    email.text = emailaddress


@_config_xmltree
def adminemail(name,
               conffile='jenkins.model.JenkinsLocationConfiguration.xml',
               _tree=None):
    """Set the jenkins admin email to `name`.

    .. code-block:: yaml

        bob@sysadmin.com:
          jenkins_config:
            - adminemail
    """
    ret = _empty_result()
    comment = 'set admin email to {0}'.format(name)
    before = _xmlpp(_tree)
    _set_admin_email(_tree, name)
    after = _xmlpp(_tree)
    changes = _changes_diff(before, after)
    if __opts__['test']:
        ret['comment'] = '\n'.join(['would ' + comment, 'diff', changes])
        return ret
    ret['comment'] = '\n'.join([comment, 'diff', changes])
    ret['result'] = True
    return ret


def test():
    fpath = '/tmp/config.xml'
    parser = etree.XMLParser(remove_blank_text=True)
    tree = etree.parse(fpath, parser=parser)
    docker_options = {
        'version': '0.15.0',
        'server_url': 'http://localhost:9876',
    }
    _insert_docker(
        tree.getroot(),
        name='hu',
        **docker_options)
    #print etree.tostring(tree,
    tree.write('/tmp/config-1.xml',
                       pretty_print=True,
                       xml_declaration=True,
                       encoding='UTF-8')

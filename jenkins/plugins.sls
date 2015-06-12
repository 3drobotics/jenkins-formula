{% from "jenkins/map.jinja" import jenkins with context %}

include:
  - jenkins

{% for name, plugin_data in jenkins.plugins.items() %}
{% set plugin_name = plugin_data.url.split('/')[-1] %}
jenkins_plugin_{{ name }}:
  file.managed:
    - name: {{ jenkins.home }}/plugins/{{ plugin_name }}
    - source: {{ plugin_data.url }}
    - source_hash: {{ plugin_data.hash }}
    - user: {{ jenkins.user }}
    - group: {{ jenkins.group }}
    - watch_in:
        - service: jenkins
{% endfor %}

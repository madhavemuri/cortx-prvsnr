{% if not salt['file.file_exists']('/opt/seagate/eos-prvsnr/generated_configs/{0}.csm'.format(grains['id'])) %}
include:
  - components.csm.prepare
  - components.csm.install
  - components.csm.config
  - components.csm.start
  - components.csm.sanity_check

Generate csm checkpoint flag:
  file.managed:
    - name: /opt/seagate/eos-prvsnr/generated_configs/{{ grains['id'] }}.csm
    - makedirs: True
    - create: True
{%- else -%}
CSM already applied:
  test.show_notification:
    - text: "Storage states already executed on node: {{ node }}. execute 'salt '*' state.apply components.csm.teardown' to reprovision these states."
{% endif %}

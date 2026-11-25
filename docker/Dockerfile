# Rundeck with Python 3, which the NodeRings plugin's scripts run on, and the plugin
# installed. Build the plugin first: python3 build.py
FROM rundeck/rundeck:6.3.0

USER root
RUN apt-get update \
 && apt-get install -y --no-install-recommends python3 \
 && rm -rf /var/lib/apt/lists/*
USER rundeck

COPY --chown=rundeck:root build/rundeck-noderings-plugin-*.zip /home/rundeck/libext/

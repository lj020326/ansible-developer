
# TODO notes

- [ ] Setup web based ansible to run/lint ansible code in __user-specified__ ansible virtual __execution environment__ docker containers.
  - code editor references (mostly flask based):
    - [flask code editor](https://github.com/lj020326/flaskcode)
    - [Online Python 3 Programming with Live Pylint Syntax Checking](https://github.com/lj020326/PythonBuddy)
    - [Hedy](https://github.com/hedyorg/hedy/tree/main)
      - [Hedy User interface](https://github.com/hedyorg/hedy/tree/main)
      - ['from website.yaml_file import YamlFile'](https://github.com/hedyorg/hedy/blob/b2fa60e82d579c6f6c46c44bc9e4b12597385f24/website/yaml_file.py#L21)
      - [persisting/marshalling of python data classes to/from yaml](https://github.com/search?q=repo%3Ahedyorg%2Fhedy%20YamlFile&type=code)
  - Run flask container behind reverse proxy
    - https://github.com/gonzalo123/flask-traefik
    - https://doc.traefik.io/traefik/middlewares/http/stripprefix/
    - https://stackoverflow.com/questions/18967441/add-a-prefix-to-all-flask-routes
    - https://flask.palletsprojects.com/en/2.3.x/config/#configuring-from-environment-variables
    - https://stackoverflow.com/questions/58633027/handling-flask-url-for-behind-nginx-reverse-proxy/59862077#59862077
    - https://serverfault.com/questions/1142373/dealing-with-flask-routing-paths-when-deployed-behind-url-prefix
    - https://docs.gunicorn.org/en/stable/settings.html
    - https://dlukes.github.io/flask-wsgi-url-prefix.html
    - https://www.reddit.com/r/flask/comments/h9cwse/nginxgunicorn_deploy_flask_app_in_nonroot_location/

- [ ] Collection development
  - https://github.com/ansible/awx-ee/blob/0.6.0/_build/requirements.yml
  - https://docs.ansible.com/ansible/latest/community/collection_development_process.html#creating-changelog-fragments
  - https://github.com/lj020326/awx-ee
  - https://github.com/ansible/awx-ee/tree/0.6.0

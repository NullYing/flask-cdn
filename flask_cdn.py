import os
from flask import url_for as flask_url_for, request
from flask import _app_ctx_stack
try:
    from urllib.parse import urlparse, urlencode, urlunparse, parse_qsl
except ImportError:
    from urlparse import urlparse, urlencode, urlunparse, parse_qsl


def url_for(endpoint, **values):
    appctx = _app_ctx_stack.top
    if appctx is None:
        raise RuntimeError('Attempted to generate a URL without the '
                           'application context being pushed. This has to be '
                           'executed when application context is available.')
    app = appctx.app

    file_name = values.get('filename')
    force_no_cdn = values.pop('_force_no_cdn', False)

    if app.config['CDN_DEBUG'] or force_no_cdn or not file_name:
        return flask_url_for(endpoint, **values)

    values['_external'] = True

    url = flask_url_for(endpoint, **values)

    pr = urlparse(url)
    query = dict(parse.parse_qsl(pr.query))

    if app.config['CDN_VERSION']:
        query.update({'v': app.config['CDN_VERSION']})
    if app.config['CDN_TIMESTAMP'] and file_name:
        path = None
        if (request.blueprint is not None and
                app.blueprints[request.blueprint].has_static_folder):
            static_files = app.blueprints[request.blueprint].static_folder
            path = os.path.join(static_files, file_name)
        if path is None or not os.path.exists(path):
            path = os.path.join(app.static_folder, file_name)
        query.update({'t': int(os.path.getmtime(path))})

    pr_list = list(pr)
    if app.config['CDN_HTTPS'] is True:
        pr_list[0] = 'https'
    pr_list[1] = app.config['CDN_DOMAIN']
    pr_list[4] = urlencode(query)
    return urlunparse(pr_list)


class CDN(object):
    """
    The CDN object allows your application to use Flask-CDN.

    When initialising a CDN object you may optionally provide your
    :class:`flask.Flask` application object if it is ready. Otherwise,
    you may provide it later by using the :meth:`init_app` method.

    :param app: optional :class:`flask.Flask` application object
    :type app: :class:`flask.Flask` or None
    """

    def __init__(self, app=None):
        """
        An alternative way to pass your :class:`flask.Flask` application
        object to Flask-CDN. :meth:`init_app` also takes care of some
        default `settings`_.

        :param app: the :class:`flask.Flask` application object.
        """
        self.app = app
        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        defaults = [('CDN_DEBUG', app.debug),
                    ('CDN_DOMAIN', None),
                    ('CDN_HTTPS', None),
                    ('CDN_TIMESTAMP', True),
                    ('CDN_VERSION', None)]

        for k, v in defaults:
            app.config.setdefault(k, v)

        if app.config['CDN_DOMAIN']:
            app.jinja_env.globals['url_for'] = url_for

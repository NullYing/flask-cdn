import os
try:
    from werkzeug.urls import url_quote
except ImportError:
    from urlparse import quote as url_quote
from werkzeug.routing import BuildError
from flask import url_for as flask_url_for
from flask import _request_ctx_stack, request, _app_ctx_stack


def url_for(endpoint, **values):

    appctx = _app_ctx_stack.top
    reqctx = _request_ctx_stack.top
    if appctx is None:
        raise RuntimeError('Attempted to generate a URL without the '
                           'application context being pushed. This has to be '
                           'executed when application context is available.')
    # ADD FOR CDN
    app = appctx.app
    force_no_cdn = values.pop('_force_no_cdn', False)
    if app.config['CDN_DEBUG'] or force_no_cdn:
        return flask_url_for(endpoint, **values)
    # ADD END

    # If request specific information is available we have some extra
    # features that support "relative" URLs.
    if reqctx is not None:
        url_adapter = reqctx.url_adapter
        blueprint_name = request.blueprint
        if not reqctx.request._is_old_module:
            if endpoint[:1] == '.':
                if blueprint_name is not None:
                    endpoint = blueprint_name + endpoint
                else:
                    endpoint = endpoint[1:]
        else:
            # TODO: get rid of this deprecated functionality in 1.0
            if '.' not in endpoint:
                if blueprint_name is not None:
                    endpoint = blueprint_name + '.' + endpoint
            elif endpoint.startswith('.'):
                endpoint = endpoint[1:]
        external = values.pop('_external', False)

    # Otherwise go with the url adapter from the appctx and make
    # the URLs external by default.
    else:
        url_adapter = appctx.url_adapter
        if url_adapter is None:
            raise RuntimeError('Application was not able to create a URL '
                               'adapter for request independent URL generation. '
                               'You might be able to fix this by setting '
                               'the SERVER_NAME config variable.')
        external = values.pop('_external', True)

    # ADD FOR CDN
    # if endpoint in app.config['CDN_ENDPOINTS']:
    external = True
    # ADD END

    anchor = values.pop('_anchor', None)
    method = values.pop('_method', None)
    scheme = values.pop('_scheme', None)
    appctx.app.inject_url_defaults(endpoint, values)

    # This is not the best way to deal with this but currently the
    # underlying Werkzeug router does not support overriding the scheme on
    # a per build call basis.
    old_scheme = None
    if scheme is not None:
        if not external:
            raise ValueError('When specifying _scheme, _external must be True')
        old_scheme = url_adapter.url_scheme
        url_adapter.url_scheme = scheme

    # ADD FOR CDN
    if not scheme and app.config['CDN_HTTPS']:
        url_adapter.url_scheme = "https"
    file_name = values.get('filename')
    if app.config['CDN_TIMESTAMP'] and file_name:
        path = None
        if (request.blueprint is not None and
                app.blueprints[request.blueprint].has_static_folder):
            static_files = app.blueprints[request.blueprint].static_folder
            path = os.path.join(static_files, file_name)
        if path is None or not os.path.exists(path):
            path = os.path.join(app.static_folder, file_name)
        values['t'] = int(os.path.getmtime(path))

    values['v'] = app.config['CDN_VERSION']
    if external:
        url_adapter = url_adapter.map.bind(app.config['CDN_DOMAIN'],
                                           url_scheme=url_adapter.url_scheme,
                                           subdomain="")
    # ADD END

    try:
        try:
            rv = url_adapter.build(endpoint, values, method=method,
                                   force_external=external)
        finally:
            url_adapter.map.subdomain = ''
            if old_scheme is not None:
                url_adapter.url_scheme = old_scheme
    except BuildError as error:
        # We need to inject the values again so that the app callback can
        # deal with that sort of stuff.
        values['_external'] = external
        values['_anchor'] = anchor
        values['_method'] = method

        return appctx.app.handle_url_build_error(error, endpoint, values)

    if anchor is not None:
        rv += '#' + url_quote(anchor)
    return rv


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
                    ('CDN_VERSION', None),
                    ('CDN_ENDPOINTS', ['static'])]

        for k, v in defaults:
            app.config.setdefault(k, v)

        if app.config['CDN_DOMAIN']:
            app.jinja_env.globals['url_for'] = url_for

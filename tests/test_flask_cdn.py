from __future__ import unicode_literals

import os
import unittest

from flask import Flask, Blueprint, render_template_string
from flask_cdn import CDN


class DefaultsTest(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.testing = True

        CDN(self.app)

    def test_debug_default(self):
        """ Tests CDN_DEBUG default value is correctly set. """
        self.assertEqual(self.app.config['CDN_DEBUG'], False)

    def test_domain_default(self):
        """ Tests CDN_DOMAIN default value is correctly set. """
        self.assertEqual(self.app.config['CDN_DOMAIN'], None)

    def test_https_default(self):
        """ Tests CDN_HTTPS default value is correctly set. """
        self.assertEqual(self.app.config['CDN_HTTPS'], None)

    def test_timestamp_default(self):
        """ Tests CDN_TIMESTAMP default value is correctly set. """
        self.assertEqual(self.app.config['CDN_TIMESTAMP'], True)


class UrlTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.testing = True

        self.app.config['CDN_DOMAIN'] = 'mycdnname.cloudfront.net'
        self.app.config['CDN_TIMESTAMP'] = False

        @self.app.route('/<url_for_string>')
        def a(url_for_string):
            return render_template_string(url_for_string)

        @self.app.route('/')
        def b():
            return render_template_string("{{ url_for('b') }}")

    def client_get(self, ufs, secure=False):
        CDN(self.app)
        client = self.app.test_client()
        if secure:
            return client.get('/%s' % ufs, base_url='https://localhost')
        else:
            return client.get('/%s' % ufs)

    def test_url_for(self):
        """ Tests static endpoint correctly affects generated URLs. """
        # non static endpoint url_for in template
        self.assertEqual(self.client_get('').get_data(True), '/')

        # static endpoint url_for in template
        ufs = "{{ url_for('static', filename='bah.js') }}"
        exp = 'http://mycdnname.cloudfront.net/static/bah.js'
        self.assertEqual(self.client_get(ufs).get_data(True), exp)

    def test_url_for_debug(self):
        """ Tests app.debug correctly affects generated URLs. """
        self.app.config['CDN_DEBUG'] = True
        ufs = "{{ url_for('static', filename='bah.js') }}"

        exp = '/static/bah.js'
        self.assertEqual(self.client_get(ufs).get_data(True), exp)

    def test_url_for_https(self):
        """ Tests CDN_HTTPS correctly affects generated URLs. """
        ufs = "{{ url_for('static', filename='bah.js') }}"

        https_exp = 'https://mycdnname.cloudfront.net/static/bah.js'
        http_exp = 'http://mycdnname.cloudfront.net/static/bah.js'

        self.app.config['CDN_HTTPS'] = True
        self.assertEqual(self.client_get(ufs, secure=True).get_data(True),
                         https_exp)
        self.assertEqual(self.client_get(ufs).get_data(True), https_exp)

        self.app.config['CDN_HTTPS'] = False
        self.assertEqual(self.client_get(ufs, secure=True).get_data(True),
                         https_exp)
        self.assertEqual(self.client_get(ufs).get_data(True), http_exp)

        self.app.config['CDN_HTTPS'] = None
        self.assertEqual(self.client_get(ufs, secure=True).get_data(True),
                         https_exp)
        self.assertEqual(self.client_get(ufs).get_data(True), http_exp)

    def test_url_for_timestamp(self):
        """ Tests CDN_TIMESTAMP correctly affects generated URLs. """
        ufs = "{{ url_for('static', filename='bah.js') }}"

        self.app.config['CDN_TIMESTAMP'] = True
        path = os.path.join(self.app.static_folder, 'bah.js')
        ts = int(os.path.getmtime(path))
        exp = 'http://mycdnname.cloudfront.net/static/bah.js?t={0}'.format(ts)
        self.assertEqual(self.client_get(ufs).get_data(True), exp)

        self.app.config['CDN_TIMESTAMP'] = False
        exp = 'http://mycdnname.cloudfront.net/static/bah.js'
        self.assertEqual(self.client_get(ufs).get_data(True), exp)

    def test_url_for_version(self):
        """ Tests that CDN_VERSION correctly affects the generated URLs. """
        ufs = "{{ url_for('static', filename='bah.js') }}"

        VERSION = '1.1-2'
        self.app.config['CDN_VERSION'] = VERSION
        path = os.path.join(self.app.static_folder, 'bah.js')
        exp = 'http://mycdnname.cloudfront.net/static/bah.js?v={0}'.format(VERSION)
        self.assertEqual(self.client_get(ufs).get_data(True), exp)

        self.app.config['CDN_VERSION'] = None
        exp = 'http://mycdnname.cloudfront.net/static/bah.js'
        self.assertEqual(self.client_get(ufs).get_data(True), exp)

    def test_for_scheme(self):
        """ Tests _scheme correctly overrides CDN_HTTPS option. """
        ufs = "{{ url_for('static', filename='bah.js', _scheme='https') }}"
        self.app.config['CDN_HTTPS'] = False
        exp = 'https://mycdnname.cloudfront.net/static/bah.js'
        self.assertEqual(self.client_get(ufs, secure=False).get_data(True),
                         exp)

        ufs = "{{ url_for('static', filename='bah.js', _scheme='http') }}"
        self.app.config['CDN_HTTPS'] = True
        exp = 'https://mycdnname.cloudfront.net/static/bah.js'
        self.assertEqual(self.client_get(ufs, secure=True).get_data(True),
                         exp)

        ufs = "{{ url_for('static', filename='bah.js', _scheme=None) }}"
        self.app.config['CDN_HTTPS'] = True
        exp = 'https://mycdnname.cloudfront.net/static/bah.js'
        self.assertEqual(self.client_get(ufs, secure=True).get_data(True),
                         exp)

    def test_force_no_cdn(self):
        """ Tests app.debug correctly affects generated URLs. """
        self.app.config['CDN_DEBUG'] = True
        ufs = "{{ url_for('static', filename='bah.js', _force_no_cdn=True) }}"

        exp = '/static/bah.js'
        self.assertEqual(self.client_get(ufs).get_data(True), exp)


class BlueprintTest(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.testing = True
        self.app.config['CDN_DOMAIN'] = 'mycdnname.cloudfront.net'
        self.app.config['CDN_TIMESTAMP'] = True
        CDN(self.app)

        test_bp = Blueprint('test_bp', 'test')

        @test_bp.route('/without_static/<url_for_string>')
        def a(url_for_string):
            return render_template_string(url_for_string)

        self.app.register_blueprint(test_bp)

        test2_bp = Blueprint('test2_bp', 'test2', static_folder=self.app.static_folder + '_bp',
                             static_url_path='/test2_bp/static')

        @test2_bp.route('/with_static/<url_for_string>')
        def b(url_for_string):
            return render_template_string(url_for_string)

        self.app.register_blueprint(test2_bp)

    def test_blueprint_without_static_folder(self):
        ufs = "{{ url_for('static', filename='bah.js') }}"
        client = self.app.test_client()
        response = client.get('/without_static/%s' % ufs)
        path = os.path.join(self.app.static_folder, 'bah.js')
        ts = int(os.path.getmtime(path))
        exp = 'http://mycdnname.cloudfront.net/static/bah.js?t={0}'.format(ts)
        self.assertEqual(response.get_data(True), exp)

    def test_blueprint_with_static_folder(self):
        ufs = "{{ url_for('test2_bp.static', filename='bah_bp.js') }}"
        client = self.app.test_client()
        response = client.get('/with_static/%s' % ufs)
        path = os.path.join(self.app.blueprints['test2_bp'].static_folder, 'bah_bp.js')
        ts = int(os.path.getmtime(path))
        exp = 'http://mycdnname.cloudfront.net/test2_bp/static/bah_bp.js?t={0}'.format(ts)
        self.assertEqual(response.get_data(True), exp)


if __name__ == '__main__':
    unittest.main()

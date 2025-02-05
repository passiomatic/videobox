"""
Implements a subset of MediaServer:1 endpoints from 
  http://upnp.org/specs/av/UPnP-av-MediaServer-v1-Device.pdf
"""
# from datetime import datetime, date, timezone
# from itertools import groupby
import base64
import os
import re
import flask
from functools import partial
from flask import current_app as app
#from playhouse.flask_utils import PaginatedQuery, get_object_or_404
# import videobox
import videobox.models as models
import videobox.media as media
from videobox import __version__
from . import bp
from http import HTTPStatus
from xml.etree import ElementTree
import videobox.dlna.queries as queries

# @bp.route('/favicon.ico')
# def favicon():
#     return '', HTTPStatus.NOT_FOUND

@bp.route('/scpd-content-directory.xml')
def scpd_content_directory_xml():
    xml = flask.render_template('dlna/scpd-content-directory.xml')
    # @@TODO application/xml
    # return flask.Response(xml, HTTPStatus.OK, mimetype='application/xml')
    return xml, {'Content-Type': 'text/xml'}


@bp.route('/scpd-connection-manager.xml')
def scpd_connection_manager_xml():
    xml = flask.render_template('dlna/scpd-connection-manager.xml')
    ## @@TODO application/xml    
    # return flask.Response(xml, HTTPStatus.OK, mimetype='application/xml')    
    return xml, {'Content-Type': 'text/xml'}

@bp.route('/description.xml')
def description_xml():
    xml = flask.render_template('dlna/description.xml', 
                                urlbase=self._urlbase, 
                                udn=self._unique_device_name, 
                                device_type=self._device_type, 
                                friendly_name=friendly_name, 
                                model_name=__service_name__, 
                                version=__version__)
    app.logger.debug(xml)
    ## @@TODO application/xml      
    #flask.Response(xml, HTTPStatus.OK, mimetype='application/xml')   
    return xml, {'Content-Type': 'text/xml'}

@bp.route('/ctrl', methods=['POST'])
def control():
    """
    Handle a SOAP command.
    """
    if 'text/xml' not in flask.request.headers['content-type']:
        return make_error_response(HTTPStatus.UNAUTHORIZED)

    def _parse():
        try:
            tree = ElementTree.fromstring(flask.request.data)
            body = tree.find(
                '{http://schemas.xmlsoap.org/soap/envelope/}Body')
            method_ = list(body)[0]
            # '{urn:schemas-upnp-org:service:ContentDirectory:1}Browse'
            uri, method_name_ = method_.tag[1:].split('}')
            return method_, method_name_
        except Exception as e:
            print('parse error', e)
        return None, None

    method, method_name = _parse()
    app.logger.debug(f"Requested SOAP action {method_name}")
    if method is None:
        return make_error_response(HTTPStatus.UNAUTHORIZED)
    if method_name != 'Browse':
        return make_error_response(HTTPStatus.UNAUTHORIZED)
    browse_flag = method.find('BrowseFlag')
    if browse_flag is None:
        return make_error_response(HTTPStatus.BAD_REQUEST)

    # @@TODO Handle BrowseMetadata flag  https://github.com/rclone/rclone/issues/3253
    browse_direct_children = browse_flag.text == 'BrowseDirectChildren'
    starting_index = int(method.find('StartingIndex').text)
    requested_count = int(method.find('RequestedCount').text)
    filter = method.find('Filter').text
    sort_criteria = method.find('SortCriteria').text
    
    object_id = method.find('ObjectID').text
    # @@TODO connect to model 
    if object_id == '0':
        series = queries.downloaded_series()
    else:    
        browse_item = models.Series.get_or_none(models.Series.id == int(object_id))
    if browse_item is None:
        return make_error_response(HTTPStatus.BAD_REQUEST)

    result, total_matches, num_returned, update_id = make_browse_response(
        browse_item, browse_direct_children, starting_index, requested_count)
    app.logger.debug(f"{'='*30}\n{result}\n{'='*30}\n")
    rendered = flask.render_template('dlna/browse_result.xml', 
                                     result=result,
                                     total_matches=total_matches, 
                                     num_returned=num_returned, 
                                     update_id=update_id)
    # app.logger.debug(f"{'='*30}\n{rendered}\n{'='*30}\n")
    return flask.Response(rendered, mimetype='text/xml')

# @bp.route('/', defaults={'path': ''})
# @bp.route('/<path:path>')
# def catch_all(path):
#     app.logger.warning(f'Could not find {path}')
#     return '', HTTPStatus.NOT_FOUND


@bp.route('/<media_file>', methods=['HEAD', 'GET'])
def media_file(media_file):
    res = flask.request.args.get('res')
    if res:
        path = base64.b64decode(res.encode()).decode('ascii')
        # @@TODO  content_dir
        app.logger.debug(f'{res=} {path=} {content_dir=}')
        return flask.send_from_directory(content_dir, res)

    item = self._file_store.get_by_id(media_file)
    if item is None:
        return '', HTTPStatus.NOT_FOUND
    _path = item.get_path()

    if flask.request.method == 'HEAD':
        if 'getcaptioninfo.sec' in flask.request.headers:
            if item.get_captions():
                response = flask.Response(
                    '', headers={'CaptionInfo.sec': item.get_captions()}, mimetype='text/html')
                return response
            response = flask.Response(
                '<html><p>Captions srt file not found</p></html>', HTTPStatus.NOT_FOUND, mimetype='text/html')
            return response

    part, start, end = get_range(flask.request.headers)
    mime_type = item.get_mime_type()

    def generate(chunk_size=2**16):  # Default to 64k chunks
        with open(_path, 'rb') as f:
            f.seek(start)
            for data in iter(partial(f.read, chunk_size), b''):
                yield data

    stats = os.stat(_path)
    end = stats.st_size if end is None else end
    size = str(end-start)

    headers = {'Content-Length': size, 'Content-Type': mime_type, 'Accept-Ranges': 'bytes',
               # DLNA.ORG_OP = Time range capable / Byte range capable
               # TV will try to read entire file without this
               'Contentfeatures.dlna.org': 'DLNA.ORG_OP=01'
               }
    if part:
        headers['Content-Range'] = f'bytes {start}-{end-1}/{size}'
    response = flask.Response(generate(
    ), HTTPStatus.PARTIAL_CONTENT if part else HTTPStatus.OK, headers=headers, direct_passthrough=True)
    # print('outbound headers', response.headers)
    return response

def get_range(headers):
    byte_range = headers.get('Range', headers.get('range'))
    match = None if not byte_range else re.match(
        r'bytes=(?P<start>\d+)-(?P<end>\d+)?', byte_range)
    if not match:
        return False, 0, None
    start = match.group('start')
    end = match.group('end')
    start = int(start)
    if end is not None:
        end = int(end)
    return True, start, end

def make_error_response(code):
    assert code in [HTTPStatus.UNAUTHORIZED, HTTPStatus.BAD_REQUEST]
    description = 'Invalid action' if code == HTTPStatus.UNAUTHORIZED else 'Invalid arguments'    
    xml = flask.render_template('dlna/browse_error.xml', code=code, description=description)
    return flask.Response(xml, HTTPStatus.INTERNAL_SERVER_ERROR, mimetype='text/xml')



def make_browse_response(browse_item: media.BaseItem, browse_direct_children: bool, starting_index: int, requested_count: int):
    object_id = browse_item.get_id()

    # Build result using Digital Item Description Language
    results_description = ElementTree.Element(
        'DIDL-Lite', xmlns='urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/')

    if browse_direct_children:
        result = browse_item.get_children(
            starting_index, starting_index + requested_count)
        for item in result:
            results_description.append(item.to_element(
                object_id, browse_direct_children))
    else:
        results_description.append(browse_item.to_element(
            object_id, browse_direct_children))

    total_matches = browse_item.get_child_count() if browse_direct_children else 1
    xml = ElementTree.tostring(results_description).decode()
    return xml, total_matches, len(results_description), browse_item.get_update_id()


# def register_devices(self, ssdp_server):
#     ssdp_server.register_local(self._unique_device_name, 'upnp:rootdevice')
#     ssdp_server.register_local(self._unique_device_name, self._device_type, f'{self._urlbase}/desc.xml')
#     for service_type in self._service_types:
#         ssdp_server.register_local(
#             self._unique_device_name, service_type)

# class VideoServer:

#     def __init__(self, host, port, content_dir, friendly_name):
#         self._unique_device_name = 'videobox'
#         self._urlbase = f'http://{host}:{port}'

#         self._device_type = 'urn:schemas-upnp-org:device:MediaServer:1'
#         self._service_types = ['urn:schemas-upnp-org:service:ContentDirectory:1', 'urn:schemas-upnp-org:service:ConnectionManager:1']


#         self._file_store = Content(content_dir, self._urlbase)
#         self._ssdp_server = SSDPServer(self)

    # @app.route('/favicon.ico')
    # def fav_icon():
    #     return '', HTTPStatus.NOT_FOUND

    # @app.route('/scpd-content-directory.xml')
    # def scpd_content_directory_xml():
    #     """ContentDirectory Service Control Point Definition"""
    #     xml = render_template('scpd-content-directory.xml')
    #     return xml, {'Content-Type': 'text/xml'}

    # @app.route('/scpd-connection-manager.xml')
    # def scpd_connection_manager_xml():
    #     """ConnectionManager Service Control Point Definition"""
    #     xml = render_template('scpd-connection-manager.xml')
    #     return xml, {'Content-Type': 'text/xml'}

    # @app.route('/ctrl', methods=['POST'])
    # def control():
    #     return self._handle_control()

    # @app.route('/desc.xml')
    # def desc_xml():
    #     xml = render_template('desc.xml', urlbase=self._urlbase, udn=self._unique_device_name, device_type=self._device_type,
    #                           friendly_name=friendly_name, model_name=__service_name__, version=__version__)
    #     #print(xml)
    #     return xml, {'Content-Type': 'text/xml'}

    # @app.route('/<media_file>', methods=['HEAD', 'GET'])
    # def media(media_file):
    #     res = request.args.get('res')
    #     if res:
    #         path = base64.b64decode(res.encode()).decode('ascii')
    #         print(f'{res=} {path=} {content_dir=}')
    #         return send_from_directory(content_dir, res)

    #     item = self._file_store.get_by_id(media_file)
    #     if item is None:
    #         return '', HTTPStatus.NOT_FOUND
    #     _path = item.get_path()

    #     if request.method == 'HEAD':
    #         if 'getcaptioninfo.sec' in request.headers:
    #             if item.get_captions():
    #                 response = Response(
    #                     '', headers={'CaptionInfo.sec': item.get_captions()}, mimetype='text/html')
    #                 return response
    #             response = Response(
    #                 '<html><p>Captions srt file not found</p></html>', HTTPStatus.NOT_FOUND, mimetype='text/html')
    #             return response

    #     part, start, end = self.get_range(request.headers)
    #     mime_type = item.get_mime_type()

    #     def generate(chunk_size=2**16):  # Default to 64k chunks
    #         with open(_path, 'rb') as f:
    #             f.seek(start)
    #             for data in iter(partial(f.read, chunk_size), b''):
    #                 yield data

    #     stats = os.stat(_path)
    #     end = stats.st_size if end is None else end
    #     size = str(end-start)

    #     headers = {'Content-Length': size, 'Content-Type': mime_type, 'Accept-Ranges': 'bytes',
    #                # DLNA.ORG_OP = Time range capable / Byte range capable
    #                # TV will try to read entire file without this
    #                'Contentfeatures.dlna.org': 'DLNA.ORG_OP=01'
    #                }
    #     if part:
    #         headers['Content-Range'] = f'bytes {start}-{end-1}/{size}'
    #     response = Response(generate(
    #     ), HTTPStatus.PARTIAL_CONTENT if part else HTTPStatus.OK, headers=headers, direct_passthrough=True)
    #     # print('outbound headers', response.headers)
    #     return response

    # @app.route('/', defaults={'path': ''})
    # @app.route('/<path:path>')
    # def catch_all(path):
    #     print('*** catch_all', path)
    #     return '', HTTPStatus.NOT_FOUND

    # @staticmethod
    # def _browse_error(code):
    #     assert code in [HTTPStatus.UNAUTHORIZED, HTTPStatus.BAD_REQUEST]
    #     rendered = render_template('browse_error.xml', code=code,
    #                                desc='Invalid Action' if code == HTTPStatus.UNAUTHORIZED else 'Invalid Args')
    #     return Response(rendered, HTTPStatus.INTERNAL_SERVER_ERROR, mimetype='text/xml')

    # def _handle_control(self):
    #     """Handle a SOAP command."""
    #     if 'text/xml' not in request.headers['content-type']:
    #         return self._browse_error(HTTPStatus.UNAUTHORIZED)

    #     def _parse():
    #         try:
    #             tree = ElementTree.fromstring(request.data)
    #             body = tree.find(
    #                 '{http://schemas.xmlsoap.org/soap/envelope/}Body')
    #             method_ = list(body)[0]
    #             # '{urn:schemas-upnp-org:service:ContentDirectory:1}Browse'
    #             uri, method_name_ = method_.tag[1:].split('}')
    #             return method_, method_name_
    #         except Exception as e:
    #             print('parse error', e)
    #         return None, None

    #     method, method_name = _parse()
    #     print(f"**Requested SOAP action {method_name}**")
    #     if method is None:
    #         return self._browse_error(HTTPStatus.UNAUTHORIZED)
    #     if method_name != 'Browse':
    #         return self._browse_error(HTTPStatus.UNAUTHORIZED)
    #     browse_flag = method.find('BrowseFlag')
    #     if browse_flag is None:
    #         return self._browse_error(HTTPStatus.BAD_REQUEST)

    #     object_id = method.find('ObjectID').text
    #     browse_item = self._file_store.get_by_id(object_id)
    #     if browse_item is None:
    #         return self._browse_error(HTTPStatus.BAD_REQUEST)
    #     browse_direct_children = browse_flag.text == 'BrowseDirectChildren'
    #     starting_index = int(method.find('StartingIndex').text)
    #     requested_count = int(method.find('RequestedCount').text)
    #     filter = method.find('Filter').text
    #     sort_criteria = method.find('SortCriteria').text

    #     result, total_matches, num_returned, update_id = self._browse(
    #         browse_item, browse_direct_children, starting_index, requested_count)
    #     print(f"{'='*30}\n{result}\n{'='*30}\n")
    #     rendered = render_template('browse_result.xml', result=result,
    #                                total_matches=total_matches, num_returned=num_returned, update_id=update_id)
    #     #print(f"{'='*30}\n{rendered}\n{'='*30}\n")
    #     return Response(rendered, mimetype='text/xml')

    # @staticmethod
    # def _browse(browse_item: BaseItem, browse_direct_children: bool, starting_index: int, requested_count: int):
    #     object_id = browse_item.get_id()

    #     # Build result using Digital Item Description Language
    #     results_description = ElementTree.Element(
    #         'DIDL-Lite', xmlns='urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/')

    #     if browse_direct_children:
    #         result = browse_item.get_children(
    #             starting_index, starting_index + requested_count)
    #         for item in result:
    #             results_description.append(item.to_element(
    #                 object_id, browse_direct_children))
    #     else:
    #         results_description.append(browse_item.to_element(
    #             object_id, browse_direct_children))

    #     total_matches = browse_item.get_child_count() if browse_direct_children else 1
    #     xml = ElementTree.tostring(results_description).decode()
    #     return xml, total_matches, len(results_description), browse_item.get_update_id()

    # @staticmethod
    # def get_range(headers):
    #     byte_range = headers.get('Range', headers.get('range'))
    #     match = None if not byte_range else re.match(
    #         r'bytes=(?P<start>\d+)-(?P<end>\d+)?', byte_range)
    #     if not match:
    #         return False, 0, None
    #     start = match.group('start')
    #     end = match.group('end')
    #     start = int(start)
    #     if end is not None:
    #         end = int(end)
    #     return True, start, end


from mpgranch import handle

def app(environ, start_response):
    """Simplest possible application object"""
    path_info = environ.get('PATH_INFO', None)
    components = path_info[1:].split('/')
    print components

    data = handle({
        'params': {
            'path': {
                'z': components[0],
                'x': components[1],
                'y': components[2],
            }
        }
    })

    status = '200 OK'
    response_headers = [
        ('Content-type','image/png'),
        ('Content-Length', str(len(data)))
    ]
    start_response(status, response_headers)
    return iter([data])

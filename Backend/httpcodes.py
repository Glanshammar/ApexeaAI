from flask import jsonify

def http_100(message="Continue"):
    return jsonify({"message": message}), 100

def http_101(message="Switching Protocols"):
    return jsonify({"message": message}), 101

def http_102(message="Processing"):
    return jsonify({"message": message}), 102

def http_103(message="Early Hints"):
    return jsonify({"message": message}), 103

def http_200(message="OK"):
    return jsonify({"message": message}), 200

def http_201(message="Created", data=None):
    if data:
        response = {"message": message}
        response.update(data if isinstance(data, dict) else {"data": data})
        return jsonify(response), 201
    return jsonify({"message": message}), 201

def http_202(message="Accepted"):
    return jsonify({"message": message}), 202

def http_203(message="Non-Authoritative Information"):
    return jsonify({"message": message}), 203

def http_204():
    return "", 204

def http_205(message="Reset Content"):
    return jsonify({"message": message}), 205

def http_206(message="Partial Content"):
    return jsonify({"message": message}), 206

def http_207(message="Multi-Status"):
    return jsonify({"message": message}), 207

def http_208(message="Already Reported"):
    return jsonify({"message": message}), 208

def http_226(message="IM Used"):
    return jsonify({"message": message}), 226

def http_300(message="Multiple Choices"):
    return jsonify({"message": message}), 300

def http_301(message="Moved Permanently"):
    return jsonify({"message": message}), 301

def http_302(message="Found"):
    return jsonify({"message": message}), 302

def http_303(message="See Other"):
    return jsonify({"message": message}), 303

def http_304(message="Not Modified"):
    return jsonify({"message": message}), 304

def http_305(message="Use Proxy"):
    return jsonify({"message": message}), 305

def http_307(message="Temporary Redirect"):
    return jsonify({"message": message}), 307

def http_308(message="Permanent Redirect"):
    return jsonify({"message": message}), 308

def http_400(message="Bad Request"):
    return jsonify({"error": message}), 400

def http_401(message="Unauthorized"):
    return jsonify({"error": message}), 401

def http_402(message="Payment Required"):
    return jsonify({"error": message}), 402

def http_403(message="Forbidden"):
    return jsonify({"error": message}), 403

def http_404(message="Not Found"):
    return jsonify({"error": message}), 404

def http_405(message="Method Not Allowed"):
    return jsonify({"error": message}), 405

def http_406(message="Not Acceptable"):
    return jsonify({"error": message}), 406

def http_407(message="Proxy Authentication Required"):
    return jsonify({"error": message}), 407

def http_408(message="Request Timeout"):
    return jsonify({"error": message}), 408

def http_409(message="Conflict"):
    return jsonify({"error": message}), 409

def http_410(message="Gone"):
    return jsonify({"error": message}), 410

def http_411(message="Length Required"):
    return jsonify({"error": message}), 411

def http_412(message="Precondition Failed"):
    return jsonify({"error": message}), 412

def http_413(message="Payload Too Large"):
    return jsonify({"error": message}), 413

def http_414(message="URI Too Long"):
    return jsonify({"error": message}), 414

def http_415(message="Unsupported Media Type"):
    return jsonify({"error": message}), 415

def http_416(message="Range Not Satisfiable"):
    return jsonify({"error": message}), 416

def http_417(message="Expectation Failed"):
    return jsonify({"error": message}), 417

def http_418(message="I'm a teapot"):
    return jsonify({"error": message}), 418

def http_421(message="Misdirected Request"):
    return jsonify({"error": message}), 421

def http_422(message="Unprocessable Entity"):
    return jsonify({"error": message}), 422

def http_423(message="Locked"):
    return jsonify({"error": message}), 423

def http_424(message="Failed Dependency"):
    return jsonify({"error": message}), 424

def http_425(message="Too Early"):
    return jsonify({"error": message}), 425

def http_426(message="Upgrade Required"):
    return jsonify({"error": message}), 426

def http_428(message="Precondition Required"):
    return jsonify({"error": message}), 428

def http_429(message="Too Many Requests"):
    return jsonify({"error": message}), 429

def http_431(message="Request Header Fields Too Large"):
    return jsonify({"error": message}), 431

def http_451(message="Unavailable For Legal Reasons"):
    return jsonify({"error": message}), 451

def http_500(message="Internal Server Error"):
    return jsonify({"error": message}), 500

def http_501(message="Not Implemented"):
    return jsonify({"error": message}), 501

def http_502(message="Bad Gateway"):
    return jsonify({"error": message}), 502

def http_503(message="Service Unavailable"):
    return jsonify({"error": message}), 503

def http_504(message="Gateway Timeout"):
    return jsonify({"error": message}), 504

def http_505(message="HTTP Version Not Supported"):
    return jsonify({"error": message}), 505

def http_506(message="Variant Also Negotiates"):
    return jsonify({"error": message}), 506

def http_507(message="Insufficient Storage"):
    return jsonify({"error": message}), 507

def http_508(message="Loop Detected"):
    return jsonify({"error": message}), 508

def http_510(message="Not Extended"):
    return jsonify({"error": message}), 510

def http_511(message="Network Authentication Required"):
    return jsonify({"error": message}), 511
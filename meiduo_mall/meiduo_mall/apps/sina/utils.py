from itsdangerous import TimedJSONWebSignatureSerializer as Serializer, BadData
from django.conf import settings



# 创建方法对openid加密
def generate_uid_signature(uid):

    # 实例化加密对象
    serializer = Serializer(secret_key=settings.SECRET_KEY,expires_in=600)
    # 把数据包装成字典
    data = {
        'uid':uid

    }
    # 对数据加密，加密后返回的数据是bytes类型
    openid_sign = serializer.dumps(data)
    # 解密
    return openid_sign.decode()


# 创建方法对openid解密
def check_uid_sign(opened_sign):
    serializer = Serializer(secret_key=settings.SECRET_KEY,expires_in=600)
    try:
        data = serializer.loads(opened_sign)
    except BadData:
        return None
    else:
        return data.get('uid')
import pickle,base64
from django_redis import get_redis_connection

def merge_cart_cookie_to_redis(request, user, response):
    """
       登录时合并购物车
       :param request: 登录时借用过来的请求对象
       :param user: 登录时借用过来的用户对象
       :param response: 借用过来准备做删除cookie的响应对象
       :return:
   """
    # 获取cookie购物车数据
    cart_str = request.COOKIES.get('carts')
    # 判断是否有cookie购物车数据,如果没有直接return
    if cart_str is None:
        return

    # 把字符串转换成字典
    cart_dict = pickle.loads(base64.b64decode(cart_str.encode()))

    """
        {
            1: {'count': 1, 'selected': True}
        }
        """
    # 创建redis连接对象
    redis_coon = get_redis_connection('carts')
    pl = redis_coon.pipeline()
    # 遍历cookie大字典
    for sku_id, sku_dict in cart_dict.items():

        # {sku_id: count}
        # 将cookie中的sku_id count 向redis的hash去存
        pl.hset('carts_%s' % user.id, sku_id, sku_dict['count'])

        # 如果当前cookie中的商品是勾选就把勾选商品sku_id向set集合添加
        if sku_dict['selected']:
            pl.sadd('selected_%s' % user.id, sku_id)
        else:
            # 如果没有勾选就从redis中移除
            pl.srem('selected_%s' % user.id, sku_id)
        # 清空cookie购物车数据
    pl.execute()
    response.delete_cookie('carts')

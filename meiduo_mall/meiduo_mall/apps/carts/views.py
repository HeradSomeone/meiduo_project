import json, pickle, base64

from django_redis import get_redis_connection
from django import http
from django.shortcuts import render
from django.views import View

from goods.models import SKU
from meiduo_mall.utils.response_code import RETCODE


class CartsView(View):
    '''购物车'''

    def post(self, request):
        '''添加购物车'''

        # 获取请求体中的sku_id, count，select状态
        user = request.user
        json_dict = json.loads(request.body.decode())
        sku_id = json_dict.get('sku_id')
        count = json_dict.get('count')
        selected = json_dict.get('selected')

        # 校验
        if all([sku_id, count]) is False:
            return http.HttpResponseForbidden('缺少必传参数')

        try:
            sku = SKU.objects.get(id=sku_id)
        except SKU.DoesNotExist:
            return http.HttpResponseForbidden('商品不存在')

        # 判断当用户是否登录还是未登录
        # 如果是登录用户存储购物车数据到redis
        # 创建redis连接对象
        response = http.JsonResponse({'code': RETCODE.OK, 'errmsg': '添加购物车成功'})
        if user.is_authenticated:
            redis_coon = get_redis_connection('carts')
            # 创建管道
            pl = redis_coon.pipeline()
            """
                hash: {sku_id_1: count, sku_id2: count}
                set: {sku_id_1, sku_id_2}
    
            """

            pl.hincrby('carts_%s' % user.id, sku_id, count)
            if selected:
                pl.sadd('selected_%s' % user.id, sku_id)

            # 执行管道
            pl.execute()
            # 响应
            # return http.JsonResponse({'code': RETCODE.OK, 'errmsg': 'OK'})
        else:
            # 如果未登录存储购物车数据到cookie

            """
            {
                sku_id_1: {'count': 2, 'selected': True},
                sku_id_2: {'count': 2, 'selected': True}
            }
            """
            # 先获取cookie购物车数据
            cart_str = request.COOKIES.get('carts')

            # 如果cookie中已有购物车数据
            # 把cookie购物车字符串转回到字典
            if cart_str:
                cart_dict = pickle.loads(base64.b64decode(cart_str.encode()))

            # 如果cookie中没有购物车数据
            # 准备一个空字典
            else:
                cart_dict = {}
            # 判断要添加的sku_id 在字典中是否存在,如果存在,需要对count做增量计算
            if sku_id in cart_dict:
                origin_count = cart_dict[sku_id]['count']
                count += origin_count
            # 添加
            cart_dict[sku_id] = {

                'count': count,
                'selected': selected

            }
            # 把购物车字典转换回字符串 然后重新设置到cookie中
            cart_str = base64.b64encode(pickle.dumps(cart_dict)).decode()
            # 响应
            response.set_cookie('carts', cart_str)
        return response

    def get(self, request):
        '''展示购物车'''
        # 判断用户是否登录
        user = request.user
        if user.is_authenticated:
            """
            登录用户获取redis购物车数据
                hash: {sku_id_1: count, sku_id2: count}
                set: {sku_id_1, sku_id_2}
            """
            # 创建redis连接对象
            redis_coon = get_redis_connection('carts')

            # 获取hash数据
            redis_hash = redis_coon.hgetall('carts_%s' % user.id)
            # 获取set数据{b'1', b'2'}
            selected_ids = redis_coon.smembers('selected_%s' % user.id)
            # 将redis购物车数据格式转换成和cookie购物车数据格式一致  目的为了后续数据查询转换代码和cookie共用一套代码
            cart_dict = {}

            for sku_id_bytes, count_bytes in redis_hash.items():
                cart_dict[int(sku_id_bytes)] = {

                    'count': int(count_bytes),
                    'selected': sku_id_bytes in selected_ids
                }
        else:
            """未登录用户获取cookie购物车数据"""
            """
            {
                sku_id_1: {'count': 2, 'selected': True},
                sku_id_2: {'count': 2, 'selected': True}
            }
            """
            # 获取cookie购物车数据
            cart_str = request.COOKIES.get('carts')
            if cart_str:
                # 判断有没有cookie购物车数据
                # 有将字符串转换成字典
                cart_dict = pickle.loads(base64.b64decode(cart_str.encode()))
            else:
                return render(request, 'cart.html')
        """
               {
                   sku_id_1: {'count': 2, 'selected': True},
                   sku_id_2: {'count': 2, 'selected': True}
               }
        """
        # 查询到购物车中所有sku_id对应的sku模型
        sku_qs = SKU.objects.filter(id__in=cart_dict.keys())

        # 创建用来装每个转换好的sku字典
        cart_skus = []

        for sku in sku_qs:
            sku_dict = {
                'id': sku.id,
                'name': sku.name,
                'price': str(sku.price),
                'default_image_url': sku.default_image.url,
                'count': int(cart_dict[sku.id]['count']),  # 方便js中的json对数据渲染
                'selected': str(cart_dict[sku.id]['selected']),
                'amount': str(sku.price * int(cart_dict[sku.id]['count']))

            }
            cart_skus.append(sku_dict)
        # 渲染

        context = {

            'cart_skus': cart_skus
        }

        return render(request, 'cart.html', context)

    def put(self, request):
        '''修改购物车'''

        # 接收数据 sku_id， count， selected
        user = request.user
        json_dict = json.loads(request.body.decode())
        sku_id = json_dict.get('sku_id')
        count = json_dict.get('count')
        selected = json_dict.get('selected')
        # 校验
        if all([sku_id, count]) is False:
            return http.HttpResponseForbidden('缺少必传参数')

        try:
            sku = SKU.objects.get(id=sku_id)
        except SKU.DoesNotExist:
            return http.HttpResponseForbidden('sku不存在')
        # 响应给前端修改后的sku数据
        cart_sku = {

            'id': sku.id,
            'name': sku.name,
            'price': sku.price,
            'default_image_url': sku.default_image.url,
            'count': int(count),  # 方便js中的json对数据渲染
            'selected': str(selected),
            'amount': sku.price * int(count)

        }
        response = http.JsonResponse({'code': RETCODE.OK, 'errmsg': 'OK', 'cart_sku': cart_sku})
        # 判断是否登录
        if user.is_authenticated:
            # 创建连接并连接到redis
            redis_coon = get_redis_connection('carts')
            pl = redis_coon.pipeline()
            # hset  # 覆盖hash中的数据
            pl.hset('carts_%s' % user.id, sku.id, count)
            # 判断selected是True还是False
            if selected:
                # 将勾选的sku_id存储到set集合
                pl.sadd('selected_%s' % user.id, sku.id)
            else:
                # 不勾选时,将sku_id从set集合中移除
                pl.srem('selected_%s' % user.id, sku.id)

            pl.execute()

        else:
            # 未登录用户修改cookie购物车数据
            # 查询cookie购物车数据
            cart_str = request.COOKIES.get('carts')
            # 判断cookie有没有值
            if cart_str:
                # 把字符串转换成字典
                cart_dict = pickle.loads(base64.b64decode(cart_str.encode()))
            else:
                # 如果cookie购物车没有数据 返回
                return http.JsonResponse({'code': RETCODE.DBERR, 'errmsg': '未获取cookies'})

            # 修改购物车大字典数据,新值覆盖旧值
            cart_dict[sku_id] = {

                'count': count,
                'selected': selected

            }
            # 将字典转换成字符串
            cart_str = base64.b64encode(pickle.dumps(cart_dict)).decode()
            # 设置cookie
            response.set_cookie('carts', cart_str)
        # 响应
        return response

    def delete(self, request):
        '''删除购物车'''
        # 接收数据 sku_id
        user = request.user
        json_dict = json.loads(request.body.decode())
        sku_id = json_dict.get('sku_id')

        # 校验
        try:
            sku = SKU.objects.get(id=sku_id)
        except SKU.DoesNotExist:
            return http.HttpResponseForbidden('sku不存在')
        # 响应给前端修改后的sku数据

        response = http.JsonResponse({'code': RETCODE.OK, 'errmsg': 'OK'})
        # 判断是否登录
        if user.is_authenticated:
            # 创建连接并连接到redis
            redis_coon = get_redis_connection('carts')
            pl = redis_coon.pipeline()
            # 删除hash中的sku_id及count
            pl.hdel('carts_%s' % user.id, sku.id)
            # 将sku_id从set集合中移除
            pl.srem('selected_%s' % user.id, sku.id)

            pl.execute()

        else:
            # 未登录用户修改cookie购物车数据
            # 查询cookie购物车数据
            cart_str = request.COOKIES.get('carts')
            # 判断cookie有没有值
            if cart_str:
                # 把字符串转换成字典
                cart_dict = pickle.loads(base64.b64decode(cart_str.encode()))
            else:
                # 如果cookie购物车没有数据 返回
                return http.JsonResponse({'code': RETCODE.DBERR, 'errmsg': '未获取cookies'})

            # 校验sku_id是否在cookies中
            if sku_id in cart_dict:
                del cart_dict[sku_id]

            # 如果数据全部删除则清除cookies
            if len(cart_dict.keys()) == 0:
                response.delete_cookie('carts')
            # 将字典转换成字符串
            cart_str = base64.b64encode(pickle.dumps(cart_dict)).decode()
            # 设置cookie
            response.set_cookie('carts', cart_str)
        # 响应
        return response


class CartsSelectAllView(View):
    '''全选购物车'''

    def put(self, request):
        # 接收数据并校验 selected
        user = request.user
        json_dict = json.loads(request.body.decode())
        selected = json_dict.get('selected')

        if isinstance(selected, bool) is False:
            return http.HttpResponseForbidden('参数有误')

        response = http.JsonResponse({'code': RETCODE.OK, 'errmsg': 'OK'})
        # 判断用户是否登录
        if user.is_authenticated:
            # 登录，创建redis连接
            redis_coon = get_redis_connection('carts')

            # 获取购物车中所有{sku_id : count }
            redis_cart = redis_coon.hgetall('carts_%s' % user.id)
            # 判断选择状态
            if selected:
                # 全选则把sku_id 全部添加到set集合中
                redis_coon.sadd('selected_%s' % user.id, *redis_cart.keys())
            else:
                # 全不选则删除 set集合
                redis_coon.delete('selected_%s' % user.id)

        else:
            # 获取购物车cookies数据
            cart_str = request.COOKIES.get('carts')
            # 判断有没有获取到cookie购物车数据
            if cart_str:
                # 如果获取到把字符串转换成字典
                cart_dict = pickle.loads(base64.b64decode(cart_str.encode()))
            else:
                # 如果没有获取到直接响应
                return http.JsonResponse({'code': RETCODE.DBERR, 'errmsg': 'cookie不存在'})

            """
                {
                    sku_id: {'count': 1, 'selected': True}
                }
            """
            # 遍历cookie购物车大字典,把里面的selected改为True或False
            for sku_id in cart_dict:
                cart_dict[sku_id]['selected'] = selected
            # 把字典转换成字符串
            cart_str = base64.b64encode(pickle.dumps(cart_dict)).decode()
            # 设置cookie
            response.set_cookie('carts', cart_str)
        # 响应
        return response


class CartsSimpleView(View):
    """展示简单的购物车数据"""

    def get(self, request):
        # 判断用户是否登录
        user = request.user
        if user.is_authenticated:
            """
            登录用户获取redis购物车数据
                hash: {sku_id_1: count, sku_id2: count}
                set: {sku_id_1, sku_id_2}
            """
            # 创建redis连接对象
            redis_coon = get_redis_connection('carts')

            # 获取hash数据
            redis_hash = redis_coon.hgetall('carts_%s' % user.id)
            # 获取set数据{b'1', b'2'}
            selected_ids = redis_coon.smembers('selected_%s' % user.id)
            # 将redis购物车数据格式转换成和cookie购物车数据格式一致  目的为了后续数据查询转换代码和cookie共用一套代码
            cart_dict = {}

            for sku_id_bytes, count_bytes in redis_hash.items():
                cart_dict[int(sku_id_bytes)] = {

                    'count': int(count_bytes),
                    'selected': sku_id_bytes in selected_ids
                }
        else:
            """未登录用户获取cookie购物车数据"""
            """
            {
                sku_id_1: {'count': 2, 'selected': True},
                sku_id_2: {'count': 2, 'selected': True}
            }
            """
            # 获取cookie购物车数据
            cart_str = request.COOKIES.get('carts')
            if cart_str:
                # 判断有没有cookie购物车数据
                # 有将字符串转换成字典
                cart_dict = pickle.loads(base64.b64decode(cart_str.encode()))
            else:
                return http.HttpResponseForbidden('cookie不存在')
        """
               {
                   sku_id_1: {'count': 2, 'selected': True},
                   sku_id_2: {'count': 2, 'selected': True}
               }
        """
        # 查询到购物车中所有sku_id对应的sku模型
        sku_qs = SKU.objects.filter(id__in=cart_dict.keys())

        # 创建用来装每个转换好的sku字典
        cart_skus = []

        for sku in sku_qs:
            sku_dict = {
                'id': sku.id,
                'name': sku.name,
                'price': str(sku.price),
                'default_image_url': sku.default_image.url,
                'count': int(cart_dict[sku.id]['count']),  # 方便js中的json对数据渲染


            }
            cart_skus.append(sku_dict)

        return http.JsonResponse({'code': RETCODE.OK, 'errmsg': 'OK', 'cart_skus': cart_skus})


from decimal import Decimal

from django.shortcuts import render
from django.views import View
from django_redis import get_redis_connection

from goods.models import SKU
from users.models import Address


class OrderSettlementView(View):
    '''订单结算'''
    def get(self, request):
        '''提供订单结算界面'''

        # 获取当前登录用户的所有收货地址
        user = request.user
        addresses = Address.objects.filter(user=user, is_deleted=False)
        # 如果有收货地址什么也不做,没有收货地址把变量设置为None
        addresses = addresses if addresses.exists() else None
        # 创建redis连接
        redis_coon = get_redis_connection('carts')
        # 获取hash所有数据{sku_id: count}
        redis_cart = redis_coon.hgetall('carts_%s' % user.id)
        # 获取set集合数据{sku_id}
        cart_selected = redis_coon.smembers('selected_%s' % user.id)
        # 准备一个字典,用来装勾选商品id及count  {1: 2}
        cart_dict = {}
        # 遍历set集合
        # 将勾选的商品sku_id 和count装入字典,并都转换为int类型
        for sku_id_bytes in cart_selected:
            cart_dict[int(sku_id_bytes)] = int(redis_cart[sku_id_bytes])

        # 通过set集合中的sku_id查询到对应的所有sku模型
        sku_qs = SKU.objects.filter(id__in=cart_dict.keys())
        # 记录总数量
        total_count = 0
        # 商品总价
        total_amount = Decimal('0.00')
        # 遍历sku_qs查询集给每个sku模型多定义count和amount属性
        for sku in sku_qs:
            # 获取当前商品的购买数量
            count = cart_dict[sku.id]
            # 把当前商品购物车数据绑定到sku模型对象上
            sku.count = count
            sku.amount = sku.price * count
            # 累加购买商品总数量
            total_count += count
            # 累加商品总价
            total_amount += sku.amount
        # 运费
        freight = Decimal('10.00')
        # 渲染数据
        '''
            'addresses': addresses,  # 用户收货地址
            'skus': sku_qs,  # 勾选的购物车商品数据
            'total_count': total_count,  # 勾选商品总数量
            'total_amount': total_amount,  # 勾选商品总价
            'freight': freight,  # 运费
            'payment_amount': total_amount + freight  # 实付款
        '''

        context = {

            'addresses': addresses,
            'skus': sku_qs,
            'total_count': total_count,
            'total_amount': total_amount,
            'freight': freight,
            'payment_amount': total_amount + freight

        }
        return render(request, 'place_order.html', context)


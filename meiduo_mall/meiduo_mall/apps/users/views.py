import re, json
from random import randint

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.shortcuts import render, redirect, reverse
from django import http
from django.views import View
from django.db import DatabaseError
import logging
from django.contrib.auth import login, authenticate, logout
from django_redis import get_redis_connection
from django.conf import settings
from itsdangerous import TimedJSONWebSignatureSerializer as Serializer

from goods.models import SKU
from meiduo_mall.utils.views import LoginRequiredView
from orders.models import OrderInfo
from .models import User, Address
from meiduo_mall.utils.response_code import RETCODE
from .utils import generate_verify_email_url, check_token_to_user
from celery_tasks.email.tasks import send_verify_email
from carts.utils import merge_cart_cookie_to_redis

logger = logging.getLogger('django')  # 创建日志输出器


class RegisterView(View):
    "注册"

    def get(self, request):
        '''提供注册界面'''

        return render(request, 'register.html')

    def post(self, request):
        '''用户注册功能'''

        # 接收前端传入的表单数据：username， password， password2， sms_code， mobile， allow
        username = request.POST.get('username')
        password = request.POST.get('password')
        password2 = request.POST.get('password2')
        sms_code = request.POST.get('sms_code')
        mobile = request.POST.get('mobile')
        allow = request.POST.get('allow')
        # 校验数据前端传入数据是否符合要求 [ ]中数据任一为 None, False, '' all返回False
        if all([username, password, password2, sms_code, mobile, allow]) is False:
            return http.HttpResponseForbidden('缺少必传参数')

        if not re.match(r'^[a-zA-Z0-9_-]{5,20}$', username):
            return http.HttpResponseForbidden('请输入5-20个字符的用户名')

        if not re.match(r'^[0-9A-Za-z]{8,20}$', password):
            return http.HttpResponseForbidden('请输入8-20位的密码')

        if password != password2:
            return http.HttpResponseForbidden('两次输入的密码不一致')

        if not re.match(r'^1[345789]\d{9}$', mobile):
            return http.HttpResponseForbidden('您输入的手机号格式不正确')

        # 短信验证码校验
        # 连接redis服务器
        redis_conn = get_redis_connection('verify_code')

        # 获取redis中暂存的短信验证码
        sms_code_server = redis_conn.get('sms_%s' % mobile)

        # 校验
        if sms_code_server is None or sms_code != sms_code_server.decode():
            return http.HttpResponseForbidden('短信验证码有误')

        # 创建一个user

        # create_user 可以自动对password进行加密
        try:
            user = User.objects.create_user(
                username=username,
                password=password,
                mobile=mobile,

            )
        except DatabaseError as e:

            logger.error(e)
            return render(request, 'register.html', {'register_errmsg': '用户注册失败'})

        # 状态保持, 注册成功直接登录

        login(request, user)  # 存储用户的ID到session中记录它到登录状态

        response = redirect('/')
        response.set_cookie('username', user.username, max_age=settings.SESSION_COOKIE_AGE)
        # 重定向到首页

        return response


class UsernameCountView(View):
    '''判断用户名是否已注册'''

    def get(self, request, username):
        # 查询当前用户名的个数 要么0要么1 1代表重复
        count = User.objects.filter(username=username).count()
        return http.JsonResponse({'code': RETCODE.OK, 'errmsg': 'OK', 'count': count})


class MobileCountView(View):
    '''判断手机号是否已注册'''

    def get(self, request, mobile):
        # 查询当前用户名的个数 要么0要么1 1代表重复
        count = User.objects.filter(mobile=mobile).count()
        return http.JsonResponse({'code': RETCODE.OK, 'errmsg': 'OK', 'count': count})


class LoginView(View):
    '''用户账号登录'''

    def get(self, request):

        return render(request, 'login.html')

    def post(self, request):
        '''账户密码登录实现逻辑'''

        # 接收用户名，密码
        username = request.POST.get('username')
        password = request.POST.get('password')
        remembered = request.POST.get('remembered')

        # 校验
        if all([username, password]) is False:
            return http.HttpResponseForbidden('缺少必传参数')
        # 登录认证
        user = authenticate(username=username, password=password)

        if user is None:
            return render(request, 'login.html', {'account_errmsg': '用户名或密码错误'})

        # if remembered != "on":
        #     settings.SESSION_COOKIE_AGE = 0 # 修改Django缓存时间 未勾选保存账号密码浏览器会话结束过期，勾选默认两周

        # # 状态保持
        # login(request, user)

        # 状态保持
        login(request, user)

        if remembered != 'on':
            request.session.set_expiry(0)

        # 响应结果重定向到首页
        response = redirect(request.GET.get('next', '/'))
        response.set_cookie('username', user.username, max_age=settings.SESSION_COOKIE_AGE)
        # 登录的时候合并购物车
        merge_cart_cookie_to_redis(request, user, response)

        return response


class LogoutView(View):
    '''退出登录'''

    def get(self, request):
        # 清除状态保持的session数据
        logout(request)

        # 重定向到login界面
        response = redirect(reverse('contents:index'))
        # 清除username的cookie
        response.delete_cookie('username')

        return response


class UserInfoView(LoginRequiredMixin, View):

    def get(self, request):
        '''提供个人信息页面'''

        # 判断是否登录（mixins.LoginRequiredMixin），登录返回用户中心界面，没有登录返回登录界面登录后进入用户中心
        # 渲染用户中心页面

        return render(request, 'user_center_info.html')


class EmailView(View):
    '''添加邮箱'''

    def put(self, request):
        # 创建put方法接收请求体中email数据json_dict
        json_dict = json.loads(request.body.decode())
        email = json_dict.get('email')

        # 校验

        if all([email]) is False:
            return http.HttpResponseForbidden('缺少邮箱数据')

        if not re.match(r'^[a-z0-9][\w\.\-]*@[a-z0-9\-]+(\.[a-z]{2,5}){1,2}$', email):
            return http.HttpResponseForbidden('邮箱格式有误')
        # 获取到user
        user = request.user

        # 设置user.email字段
        user.email = email

        # 调用save保存
        user.save()

        # 发送邮件到email
        verify_url = generate_verify_email_url(user)
        send_verify_email(email, verify_url)

        # 响应
        return http.JsonResponse({'code': RETCODE.OK, 'errmsg': 'OK'})


class VerifyEmailView(View):
    '''激活邮箱'''

    def get(self, request):
        """实现激活邮箱逻辑"""
        # 获取token
        token = request.GET.get('token')

        # 解密并获取到user
        user = check_token_to_user(token)
        if user is None:
            return http.HttpResponseForbidden('token无效')

        # 修改当前user.email_active=True
        user.email_active = True
        user.save()

        # 响应
        return redirect('/info/')


class AddressView(LoginRequiredMixin, View):
    """用户收货地址"""

    def get(self, request):
        """提供用户收货地址界面"""
        # 获取当前用户的所有收货地址
        user = request.user
        # address = user.addresses.filter(is_deleted=False)  # 获取当前用户的所有收货地址
        address_qs = Address.objects.filter(is_deleted=False, user=user)  # 获取当前用户的所有收货地址

        address_list = []
        for address in address_qs:
            address_dict = {
                'id': address.id,
                'title': address.title,
                'receiver': address.receiver,
                'province_id': address.province_id,
                'province': address.province.name,
                'city_id': address.city_id,
                'city': address.city.name,
                'district_id': address.district_id,
                'district': address.district.name,
                'place': address.place,
                'mobile': address.mobile,
                'tel': address.tel,
                'email': address.email,
            }
            address_list.append(address_dict)

        context = {
            'addresses': address_list,
            'default_address_id': user.default_address_id
        }
        return render(request, 'user_center_site.html', context)


class CreateAddressView(View):
    '''新增收货地址'''

    def post(self, request):
        '''实现新增收货地址逻辑'''

        # 判断是否超过地址上限：最多20个
        user = request.user
        count = Address.objects.filter(user=user, is_deleted=False).count()
        if count >= 20:
            return http.HttpResponseForbidden('地址超过20个')
        # 接收数据

        json_dict = json.loads(request.body.decode())
        title = json_dict.get('title')
        receiver = json_dict.get('receiver')
        province_id = json_dict.get('province_id')
        city_id = json_dict.get('city_id')
        district_id = json_dict.get('district_id')
        place = json_dict.get('place')
        mobile = json_dict.get('mobile')
        tel = json_dict.get('tel')
        email = json_dict.get('email')

        # 校验数据
        if all([receiver, province_id, city_id, district_id, place, mobile]) is False:
            return http.HttpResponseForbidden('缺少必传参数')

        if not re.match(r'^1[3-9]\d{9}$', mobile):
            return http.HttpResponseForbidden('参数mobile有误')
        if tel:
            if not re.match(r'^(0[0-9]{2,3}-)?([2-9][0-9]{6,7})+(-[0-9]{1,4})?$', tel):
                return http.HttpResponseForbidden('参数tel有误')
        if email:
            if not re.match(r'^[a-z0-9][\w\.\-]*@[a-z0-9\-]+(\.[a-z]{2,5}){1,2}$', email):
                return http.HttpResponseForbidden('参数email有误')

        # 保存地址
        try:
            address = Address.objects.create(
                user=user,
                title=title,
                receiver=receiver,
                province_id=province_id,
                city_id=city_id,
                district_id=district_id,
                place=place,
                mobile=mobile,
                tel=tel,
                email=email
            )
        except Exception as e:
            logger.error(e)
            return http.JsonResponse({'code': RETCODE.DBERR, 'errmsg': '地址添加失败'})

        # 判断是否有默认地址，没有则添加
        if not user.default_address:
            user.default_address = address
            user.save()

        # 响应添加地址到前端

        address_dict = {
            'id': address.id,
            'title': address.title,
            'receiver': address.receiver,
            'province_id': address.province_id,
            'province': address.province.name,
            'city_id': address.city_id,
            'city': address.city.name,
            'district_id': address.district_id,
            'district': address.district.name,
            'place': address.place,
            'mobile': address.mobile,
            'tel': address.tel,
            'email': address.email,

        }
        return  http.JsonResponse({'code': RETCODE.OK, 'errmsg': 'OK', 'address': address_dict})


class UpdateDestroyAddressView(LoginRequiredView):
    """修改和删除"""
    def put(self,request, address_id):
        """修改地址逻辑"""
        # 查询要修改的地址对象
        address = Address.objects.get(id=address_id)
        # 判断是否存在该address_id
        if address_id is None:
            return http.HttpResponseForbidden('修改的地址不存在')
        # 接收数据
        json_dict = json.loads(request.body.decode())
        title = json_dict.get('title')
        receiver = json_dict.get('receiver')
        province_id = json_dict.get('province_id')
        city_id = json_dict.get('city_id')
        district_id = json_dict.get('district_id')
        place = json_dict.get('place')
        mobile = json_dict.get('mobile')
        tel = json_dict.get('tel')
        email = json_dict.get('email')

        # 校验
        if all([title, receiver, province_id, city_id, district_id, place, mobile]) is False:
            return http.HttpResponseForbidden('缺少必传参数')
        if not re.match(r'^1[3-9]\d{9}$', mobile):
            return http.HttpResponseForbidden('参数mobile有误')
        if tel:
            if not re.match(r'^(0[0-9]{2,3}-)?([2-9][0-9]{6,7})+(-[0-9]{1,4})?$', tel):
                return http.HttpResponseForbidden('参数tel有误')
        if email:
            if not re.match(r'^[a-z0-9][\w\.\-]*@[a-z0-9\-]+(\.[a-z]{2,5}){1,2}$', email):
                return http.HttpResponseForbidden('参数email有误')
        # 修改数据
        Address.objects.filter(id=address_id).update(

            title=title,
            receiver=receiver,
            province_id=province_id,
            city_id=city_id,
            district_id=district_id,
            place=place,
            mobile=mobile,
            tel=tel,
            email=email,
        )
        # 重查address_id
        address = Address.objects.get(id=address_id)
        # 响应数据
        address_dict={
            'title':address.title,
            'receiver':address.receiver,
            'province_id':address.province_id,
            'city_id':address.city_id,
            'district_id':address.district_id,
            'place':address.place,
            'mobile':address.mobile,
            'tel':address.tel,
            'email':address.email,
        }
        return http.JsonResponse({'code': RETCODE.OK, 'errmsg': 'OK', 'address': address_dict})


    def delete(self, request, address_id):
        """对收货地址逻辑删除"""
        address = Address.objects.get(id=address_id)

        try:
            address.is_deleted = True
        except Address.DoesNotExist:

            return http.HttpResponseForbidden('地址删除失败')

        address.save()
        return http.JsonResponse({'code': RETCODE.OK, 'errmsg': 'OK'})


class DefaultAddressView(LoginRequiredView):
    """设置默认地址"""

    def put(self, request, address_id):
        """实现默认地址"""
        try:
            address = Address.objects.get(id=address_id)
        except Address.DoesNotExist:
            return http.HttpResponseForbidden('要修改的地址不存在')

        user = request.user
        user.default_address = address
        user.save()

        return http.JsonResponse({'code': RETCODE.OK, 'errmsg': 'OK'})


class UpdateTitleAddressView(LoginRequiredView):
    """修改用户收货地址标题"""
    def put(self, request, address_id):

        try:
            address = Address.objects.get(id=address_id)
        except Address.DoesNotExist:
            return http.HttpResponseForbidden('修改的地址不存在')

        json_dict = json.loads(request.body.decode())
        title = json_dict.get('title')
        address.title = title
        address.save()

        return http.JsonResponse({'code': RETCODE.OK, 'errmsg': 'OK'})


class ChangePasswordView(LoginRequiredView):
    '''修改密码'''

    def get(self, request):

        return render(request, 'user_center_pass.html')

    def post(self, request):
        '''实现修改密码逻辑'''

        # 获取数据
        user = request.user
        old_password = request.POST.get('old_pwd')
        password = request.POST.get('new_pwd')
        password2 = request.POST.get('new_cpwd')

        # 校验
        if all([old_password, password, password2]) is False:
            return http.HttpResponseForbidden('缺少必传参数')

        if user.check_password(old_password) is False:
            return render(request, 'user_center_pass.html',{'origin_pwd_errmsg': '原始密码错误'})


        if not re.match(r'^[0-9A-Za-z]{8,20}$', password):
            return http.HttpResponseForbidden('密码最少8位，最长20位')
        if password != password2:
            return http.HttpResponseForbidden('两次输入的密码不一致')

        # 修改数据
        user.set_password(password)
        user.save()

        # 响应重定向
        logout(request)
        response = redirect('/login/')
        response.delete_cookie('username')
        print(response)

        return response


class UserBrowseHistory(View):
    '''用户浏览记录'''

    def post(self, request):
        # 判断当前用户是否登录
        user = request.user
        if not user.is_authenticated:
            return http.HttpResponseForbidden('用户未登录')

        # 获取请求体中的sku_id
        json_dict = json.loads(request.body.decode())
        sku_id = json_dict.get('sku_id')

        # 检验sku_id
        try:
            sku = SKU.objects.get(id=sku_id)
        except SKU.DoesNotExist:
            return http.HttpResponseForbidden('商品不存在')

        # 创建redis连接对象
        redis_coon = get_redis_connection('history')
        pl = redis_coon.pipeline()
        key = 'history_%s' % user.id
        # 先去重
        pl.lrem(key, 0 , sku_id)
        # 存储到列表的开头
        pl.lpush(key, sku_id)
        # 截取前5个
        pl.ltrim(key, 0, 4)
        # 执行管道
        pl.execute()
        # 响应
        return http.JsonResponse({'code': RETCODE.OK, 'errmsg': 'OK'})

    def get(self, request):
        '''查询用户浏览记录'''

        user = request.user
        # 创建redis连接对象
        redis_coon = get_redis_connection('history')

        # 获取当前登录用户的浏览记录列表数据 [sku_id1, sku_id2]
        sku_id_qs = redis_coon.lrange('history_%s' % user.id, 0, -1)

        # 通过sku_id查询sku,再将sku模型转换成字典
        # 用来装每一个sku字典
        skus = []
        for sku_id in sku_id_qs:
            sku = SKU.objects.get(id=sku_id)
            sku_dict = {

                'id': sku.id,
                'name': sku.name,
                'default_image_url': sku.default_image.url,
                'price': sku.price

            }
            skus.append(sku_dict)
        # 响应
        return http.JsonResponse({'code': RETCODE.OK, 'errmsg': 'OK', 'skus': skus})


class UserOrderInfoView(LoginRequiredView):
    '''我的订单'''

    def get(self, request, page_num):
        # 查询当前登录用户的所有订单
        user = request.user
        order_qs = OrderInfo.objects.filter(user=user).order_by('-create_time')

        for order_model in order_qs:
            # 给每个订单多定义两个属性, 订单支付方式中文名字, 订单状态中文名字
            order_model.pay_method_name = OrderInfo.PAY_METHOD_CHOICES[order_model.pay_method - 1][1]
            order_model.status_name = OrderInfo.ORDER_STATUS_CHOICES[order_model.status - 1][1]
            # 再给订单模型对象定义sku_list属性,用它来包装订单中的所有商品
            order_model.sku_list = []
            # 获取订单中的所有商品
            order_goods = order_model.skus.all()
            # 遍历订单中所有商品查询集
            for order_good in order_goods:
                # 获取到订单商品所对应的sku
                sku = order_good.sku
                # 绑定它买了几件
                sku.count = order_good.count
                # 给sku绑定一个小计总额
                sku.amount = sku.price * sku.count
                # 把sku添加到订单sku_list列表中
                order_model.sku_list.append(sku)

        # 创建分页器对订单数据进行分页
        # 创建分页对象
        paginator = Paginator(order_qs, 2)
        # 获取指定页的所有数据
        page_orders = paginator.page(page_num)
        # 获取总页数
        total_page = paginator.num_pages
        # 渲染数据
        context = {

            'page_orders': page_orders,# 当前这一页要显示的所有订单数据
            'page_nun': page_num, # 当前是第几页
            'total_page': total_page# 总页数

        }

        return render(request, 'user_center_order.html', context)


class ShowFindPassword(View):
    '''找回密码页面渲染'''

    def get(self,request):


        return render(request, 'find_password.html')


class CheckUsername(View):
    '''验证用户名'''

    def get(self, request, username):

        text = request.GET.get('text')
        image_code_id = request.GET.get('image_code_id')

        redis_coon = get_redis_connection('verify_code')
        redis_image = redis_coon.get('img_%s' % image_code_id)
        if redis_image.decode().lower() != text.lower():
            return http.JsonResponse({'message':'验证码错误'},status=400)
        else:
            try:
                user = User.objects.get(username=username)
            except User.DoesNotExist:
                return http.JsonResponse({'message':'用户错误'},status=404)

            serializer = Serializer(settings.SECRET_KEY, 300)
            data = {

                'mobile': user.mobile

            }
            access_token = serializer.dumps(data).decode()

            context = {

                'mobile': user.mobile,
                'access_token': access_token

            }
            return http.JsonResponse(context)


class MobileCode(View):
    '''获取短信验证码'''

    def get(self, request,):

        access_token = request.GET.get('access_token')

        serializer = Serializer(settings.SECRET_KEY, 300)

        data = serializer.loads(access_token)

        mobile = data['mobile']

        redis_conn = get_redis_connection('verify_code')

        sms_code = '%06d' % randint(0,999999)
        logger.info(sms_code)

        redis_conn.setex('sms_%s' % mobile, 300, sms_code)

        return http.JsonResponse({'message': 'OK'})


class CheckMobile(View):
    '''校验短信验证码'''

    def get(self, request, username):

        user = User.objects.get(username=username)
        sms_code = request.GET.get('sms_code')
        mobile = user.mobile

        redis_conn = get_redis_connection('verify_code')
        redis_sms_code = redis_conn.get('sms_%s' %mobile)

        if sms_code is None or sms_code != redis_sms_code.decode():
            return http.JsonResponse({'message': '短信验证码错误'},status=400)
        else:
            serializer = Serializer(settings.SECRET_KEY, 300)
            data = {


                'mobile': user.mobile,

            }
            access_token = serializer.dumps(data).decode()

            context = {
                'user_id': user.id,
                'access_token': access_token
            }
            return http.JsonResponse(context)


class SetNewPwd(View):
    '''设置新密码'''

    def post(self, request, user_id):

        json_dict = json.loads(request.body.decode())
        password = json_dict.get('password')
        password2 = json_dict.get('password2')
        access_token = json_dict.get('access_token')

        serializer = Serializer(settings.SECRET_KEY, 300)
        data = serializer.loads(access_token)
        mobile = data['mobile']
        try:
            user = User.objects.get(mobile=mobile)
        except User.DoesNotExist:
            return http.JsonResponse({'message':'用户错误'},status=404)

        if all([password, password2, access_token]) is False:
            return http.HttpResponseForbidden('缺少必传参数')

        if not re.match(r'^[0-9A-Za-z]{8,20}$', password):
            return http.HttpResponseForbidden('请输入8-20位的密码')

        if password != password2:
            return http.HttpResponseForbidden('两次输入的密码不一致')

        user.set_password(password)
        user.save()
        # response = redirect('/login/')

        return http.JsonResponse({'message': 'OK'})




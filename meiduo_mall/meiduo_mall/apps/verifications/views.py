from django.shortcuts import render
from django.views import View
from meiduo_mall.libs.captcha.captcha import captcha
from django_redis import get_redis_connection
from django import http
from random import randint
from meiduo_mall.utils.response_code import RETCODE
import logging
from meiduo_mall.libs.yuntongxun.sms import CCP
from . import constants
from celery_tasks.sms.tasks import send_sms_code
# Create your views here.
logger = logging.getLogger('django')
class ImageCodeView(View):
    '''生成图形验证码'''

    def get(self, request, uuid):
        """
        :param uuid: 唯一标识，用来区分当前的用户是哪一个
        :return:
        """
        # 利用SDK生成图形验证码 （唯一标识字符串，图形验证码内容字符串，二进制图片数据）
        name, text, image = captcha.generate_captcha()
        # 创建redis连接对象
        redis_conn = get_redis_connection('verify_code')
        # 将图形验证码字符串存入到redis
        redis_conn.setex('img_%s' % uuid, constants.IMAGE_CODE_REDIS_EXPIRES, text)
        # 把生成好的图片响应给前端
        return http.HttpResponse(image, content_type='image/jpg')


class SMSCodeView(View):
    '''短信验证码'''

    def get(self, request, mobile):
        """
        :param mobile: 接收短信的手机号
        :return:
        """
        # 每次发短信验证码之前先拿当前要发短信的手机号获取redis的短信标记，如果没有标记就发，有标记提前响应
        # 创建redis连接对象
        redis_conn = get_redis_connection('verify_code')
        send_flag = redis_conn.get('send_flag_%s' % mobile)

        # 校验标记
        if send_flag:
            return http.JsonResponse({'code': RETCODE.THROTTLINGERR, 'errmsg': '频繁发送短信'})

        # 接收到前端传入的mobile， image_code, uuid
        image_code_client = request.GET.get('image_code')
        uuid = request.GET.get('uuid')

        # 判断参数是否齐全
        if all([image_code_client, uuid]) is False:
            return http.JsonResponse({'code': RETCODE.NECESSARYPARAMERR, 'errmsg':'缺少必传参数'})

        # 根据uuid作为key 获取到redis中当前用户的图形验证值
        image_code_server = redis_conn.get('img_%s' % uuid)

        # 删除图形验证码，避免恶意测试图形验证码
        redis_conn.delete('img_%s' % uuid)

        # 从redis中取出的数据都是byte类型，需要decode解码
        # 判断用户写的图形验证码和redis存的是否一致
        if image_code_client is None or image_code_client.lower() != image_code_server.decode().lower():
            return http.JsonResponse({'code': RETCODE.IMAGECODEERR, 'errmsg':'验证码错误'})

        # 发送短信
        # 利用随机数生成一个6位数
        sms_code = '%06d' % randint(0,999999)
        logger.info(sms_code)

        # 创建Redis管道
        pl = redis_conn.pipeline()

        # 将Redis请求添加到队列
        # 将生成好的短信验证码也存储到redis，以备后期校验

        # redis_conn.setex('sms_%s' % mobile, constants.SMS_CODE_REDIS_EXPIRES, sms_code)
        pl.setex('sms_%s' % mobile, constants.SMS_CODE_REDIS_EXPIRES, sms_code)

        # 手机发送验证码后在redis设置一个标记 计时60秒，防止刷新重发

        # redis_conn.setex('send_flag_%s' % mobile, 60, 1)
        pl.setex('send_flag_%s' % mobile, 60, 1)

        # 执行请求

        pl.execute()

        # # 利用SDK容联云发短信
        # CCP().send_template_sms(手机号, [验证码, 提示用户验证码有效期为多少分钟], 短信模版ID)
        # CCP().send_template_sms(mobile, [sms_code, constants.SMS_CODE_REDIS_EXPIRES // 60], constants.SEND_SMS_TEMPLATE_ID)

        # 需要把CCP这行代码先加入到一个指定的仓库中，后续在单独的一个线程 进程去异步执行， 不在当下去执行
        # 由生产者 往经纪人里面存任务

        send_sms_code.delay(mobile, sms_code)


        # 响应
        return http.JsonResponse({'code': RETCODE.OK, 'errmsg': '短信发送成功'})
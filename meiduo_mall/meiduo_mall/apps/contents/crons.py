from .models import ContentCategory
from .utils import get_categories
from django.shortcuts import render
from django.conf import settings
import os
from django.template import loader
import time

def generate_static_index_html():
    contents = {}  # 用来装所有广告数据的字典
    print('%s: generate_static_index_html' % time.ctime())

    contentCategory_qs = ContentCategory.objects.all()  # 获取所有广告类别数据

    for category in contentCategory_qs:
        contents[category.key] = category.content_set.filter(status=True).order_by('sequence')

    context = {
        'categories': get_categories(),
        'contents': contents

    }

    # response = render(None, 'index.html', context)
    # html_text = response.content.decode()  # 获取响应体数据
    template = loader.get_template('index.html')  # 加载模板文件
    html_text = template.render(context)  # 渲染模板
    file_path = os.path.join(settings.STATICFILES_DIRS[0], 'index.html')
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(html_text)
#!/alidata/Envs/prometheus/bin/python3
#coding=utf-8
import json
import yaml
import shutil

from aliyunsdkcore.client import AcsClient
from aliyunsdkecs.request.v20140526.DescribeInstancesRequest import DescribeInstancesRequest


ENV_LIST = (
    "PRO", # 生产环境
    "HUI", # 灰度环境
    "QA",  # 测试QA环境
    "RELEASE",  # 测试RELEASE
    "DEV",  # DEV开发环境
    "OTHER"  # 主机环境未分类
)


class ECSMeta():
    """ECS元数据类"""
    def __init__(self, instance):
        # node_exporter的默认端口是20001
        self.port = "20001"
        # 设置服务器的IP  
        if len(instance["VpcAttributes"]["PrivateIpAddress"]["IpAddress"]) > 0: 
            # 当该机器是vpc网络下的机器的时候，以私网IP为准
            self.ip = instance["VpcAttributes"]["PrivateIpAddress"]["IpAddress"][0]
        elif len(instance["PublicIpAddress"]["IpAddress"]):
            # 当该机器是经典网络下的机器的时候，以公网IP为准，而不是内网IP
            self.ip = instance["PublicIpAddress"]["IpAddress"][0]
        else:
             pass
        # 设置服务器的系统
        self.os_name = instance["OSName"]
        # 设置实例名称
        self.instance_name = (instance["InstanceName"])
        # 设置机器的实例ID，该id是一个云资源的唯一标识
        self.instance_id = instance["InstanceId"]
        # 初始化自己的环境为OTHER，OTHER表示环境为分类的主机
        self.env = "OTHER"
        # 按理来说，应该在阿里云为每一台机器添加tag，然后按照tag中设置的env来拿到当前主机所处的环境
        # 但是目前来讲所有机器并没有设置一个规范的标签tag，或者说有的机器并没有设置tag标签，因此判断较为困难
        # 因此这里仅仅是看足迹的名称中是否包含对应的环境变量来判断，如果有的话那么就配置上，没有的话就保持other
        # 建议规范化以后重新考虑该值的取值和设定
        for env in ENV_LIST:
            if env in str.upper(self.instance_name) : 
                self.env = env
                break


class ECSInfo():
    
    def __init__(self):
        """初始化构造函数"""
        self.client = AcsClient('<your_access_key>', '<your_access_secret>', 'cn-beijing')
        self.req = DescribeInstancesRequest()
        self.PageSize = 100
        # 指定要写入的配置文件名称
        self.file="/usr/local/prometheus/targets/nodes/ecs_node.yaml"
        # 指定要备份的目录位置
        self.bak="/usr/local/prometheus/targets/nodes/"

    def info_template(self, page_num=1):
        
        to_list = lambda data: data["Instances"]["Instance"]
        # 初始化一个信息结果的列表
        self.info_result = [] 
        for instance in self.pager_generator(page_num, to_list):
            ecs_meta_info = ECSMeta(instance)
            target_info = {
                "targets": ["{0}:{1}".format(ecs_meta_info.ip, ecs_meta_info.port), ],
                "labels": {
                    "osname": ecs_meta_info.os_name,
                    "instancename": ecs_meta_info.instance_name,
                    "instanceid": ecs_meta_info.instance_id,
                    "env": ecs_meta_info.env
                }
            }
            self.info_result.append(target_info)
    
    def write_info(self, backup=True):
        if backup:
            try:
                shutil.copyfile(self.file, self.bak + "ecs_node.yaml.bak")
            except Exception:
                pass 
        with open(self.file, 'w', encoding="utf-8") as file_handler : 
            yaml.dump(self.info_result, file_handler, default_flow_style=False, allow_unicode=True)
     
    # 获取所有ECS元数据列表
    def pager_generator(self, page_num, to_list):
        # 构建一个分页用的生成器，因为所有的ecs可能一次请求是拿不完的，因此需要做分页的请求，默认的页码数是100
        self.req.set_PageSize(self.PageSize)
        # 循环取数据
        while True:
            # 首次默认的页码号为1
            self.req.set_PageNumber(page_num)
            resp = self.client.do_action_with_exception(self.req)
            # 通过接口拿到的数据是bytes类型，所以要转换一下
            data = json.loads(resp)
            # 使用to_list拿到对应的实例列表
            instances = to_list(data)
            for instance in instances:
                yield instance
            # 仅当本次请求返回的页码数小于分页大小的时候，那么说明这是最后一页了，跳出循环
            if len(instances) < self.PageSize:
                break
            # 如果不是最后一页的话，那么继续页码数+1，继续循环请求
            page_num += 1

def main():
    """程序入口函数"""
    # 初始化一个EcsInfo实例对象
    ecs_info  = ECSInfo()
    # 拿到要采集的所有ecs元数据信息
    ecs_info.info_template()
    # 将元数据信息写入对应的文件
    ecs_info.write_info()


if __name__ == "__main__":
    main()

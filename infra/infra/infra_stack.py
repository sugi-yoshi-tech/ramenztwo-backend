import os
from aws_cdk import (
    Stack,
    aws_ec2 as ec2,
    aws_ecs as ecs,
    aws_elasticloadbalancingv2 as elbv2,
    aws_logs as logs,
    CfnOutput,
    RemovalPolicy,
    Duration,         
    IgnoreMode
)
from constructs import Construct

class InfraStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # 1. ネットワーク環境(VPC)の作成
        vpc = ec2.Vpc(self, "MyVpc",
            max_azs=2,
            nat_gateways=1,
        )

        # 2. ECSクラスターの作成
        cluster = ecs.Cluster(self, "MyCluster",
            vpc=vpc
        )

        # ### 修正点 1: LogGroupを事前に定義 ###
        # バックエンド用のロググループを作成
        backend_log_group = logs.LogGroup(self, "BackendLogGroup",
            log_group_name="/ecs/my-app/backend",
            removal_policy=RemovalPolicy.DESTROY # スタック削除時に自動で削除
        )
        
        # フロントエンド用のロググループを作成
        frontend_log_group = logs.LogGroup(self, "FrontendLogGroup",
            log_group_name="/ecs/my-app/frontend",
            removal_policy=RemovalPolicy.DESTROY
        )

        # 3. バックエンドサービスの定義 (FastAPI)
        backend_task_definition = ecs.FargateTaskDefinition(self, "BackendTaskDef",
            memory_limit_mib=512,
            cpu=256
        )

        backend_task_definition.add_container("BackendContainer",
            image=ecs.ContainerImage.from_asset("../", file="Dockerfile.backend",ignore_mode=IgnoreMode.DOCKER,),
            port_mappings=[ecs.PortMapping(container_port=8000)],
            environment={
                "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY", ""),
                "PRTIMES_ACCESS_TOKEN": os.getenv("PRTIMES_ACCESS_TOKEN", ""),
                "OPENAI_MODEL": os.getenv("OPENAI_MODEL", "gpt-4o")
            },
            # ### 修正点 1: 作成したLogGroupオブジェクトを渡す ###
            logging=ecs.LogDrivers.aws_logs(
                stream_prefix="ecs-backend",
                log_group=backend_log_group 
            )
        )
        
        # 4. フロントエンドサービスの定義 (Streamlit)
        frontend_task_definition = ecs.FargateTaskDefinition(self, "FrontendTaskDef",
            memory_limit_mib=512,
            cpu=256
        )

        frontend_container = frontend_task_definition.add_container("FrontendContainer",
            image=ecs.ContainerImage.from_asset("../", file="Dockerfile.frontend",ignore_mode=IgnoreMode.DOCKER,),
            port_mappings=[ecs.PortMapping(container_port=8501)],
            # ### 修正点 1: 作成したLogGroupオブジェクトを渡す ###
            logging=ecs.LogDrivers.aws_logs(
                stream_prefix="ecs-frontend",
                log_group=frontend_log_group
            )
        )

        # 5. ロードバランサー(ALB)とECSサービスの作成
        backend_service = ecs.FargateService(self, "BackendService",
            cluster=cluster,
            task_definition=backend_task_definition,
            desired_count=1
        )
        
        frontend_service = ecs.FargateService(self, "FrontendService",
            cluster=cluster,
            task_definition=frontend_task_definition,
            desired_count=1
        )

        alb = elbv2.ApplicationLoadBalancer(self, "MyAlb",
            vpc=vpc,
            internet_facing=True
        )

        listener = alb.add_listener("Listener", port=80)

        # 6. ALBのルーティング設定
        listener.add_targets("FrontendTarget",
            port=80,
            targets=[frontend_service.load_balancer_target(
                container_name="FrontendContainer",
                container_port=8501
            )],
            health_check={
                "path": "/",
                # ### 修正点 2: Durationクラスを使用して時間間隔を指定 ###
                "interval": Duration.seconds(30),
            }
        )

        # `add_action` を使うとより柔軟な設定が可能ですが、ここでは`add_targets`のpriorityを使います
        listener.add_targets("BackendApiTarget",
            priority=1,
            port=80,
            targets=[backend_service.load_balancer_target(
                container_name="BackendContainer",
                container_port=8000
            )],
            conditions=[
                elbv2.ListenerCondition.path_patterns(["/companies*", "/analyze*"])
            ],
            health_check={
                "path": "/companies",
                # ### 修正点 2: Durationクラスを使用して時間間隔を指定 ###
                "interval": Duration.seconds(30),
            }
        )
        
        # フロントエンドのコンテナにALBのDNS名を環境変数として渡す
        frontend_container.add_environment("API_BASE_URL", f"http://{alb.load_balancer_dns_name}")

        # 7. 出力
        CfnOutput(self, "LoadBalancerDNS", value=alb.load_balancer_dns_name)
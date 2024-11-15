import os

from aws_cdk import Stack, Environment, RemovalPolicy, CfnOutput
from aws_cdk import aws_s3 as s3
from aws_cdk.aws_s3 import (
    BucketAccessControl,
    BucketEncryption, 
    BlockPublicAccess
)
from aws_cdk.aws_s3_deployment import BucketDeployment, Source
from aws_cdk.aws_route53 import HostedZone
from aws_cdk.aws_certificatemanager import Certificate, CertificateValidation
from aws_cdk.aws_cloudfront import (
    BehaviorOptions,
    Distribution,
    OriginAccessIdentity,
    ViewerProtocolPolicy,
)
# TODO: Update S3Origin to something not set to be deprecated:
# `S3BucketOrigin` or `S3StaticWebsiteOrigin`
from aws_cdk.aws_cloudfront_origins import S3Origin
from constructs import Construct


DOMAIN_NAME = "unleashedlab.io"
SITE_SOURCES_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "site"
)


class WebsiteStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        """ Initialize Website stack for deployment via CloudFormation.

            Helpful links:
            - https://docs.aws.amazon.com/AmazonS3/latest/userguide
              /website-hosting-custom-domain-walkthrough.html        
        """

        super().__init__(scope, construct_id, **kwargs)

        # First we need a Bucket and a Deployment for the Bucket with our
        # website sources
        website_bucket = s3.Bucket(
            self,
            id = "website_bucket",
            versioned = True,
            website_index_document="index.html",
            access_control=BucketAccessControl.PRIVATE,
            encryption=BucketEncryption.S3_MANAGED,
            block_public_access=BlockPublicAccess.BLOCK_ALL,
            enforce_ssl=True,
            removal_policy=RemovalPolicy.RETAIN
        )

        deployment = BucketDeployment(
            self,
            id = "website_deployment",
            destination_bucket = website_bucket,
            sources = [Source.asset(SITE_SOURCES_PATH)]
        )

        # Then we need the website domain's Hosted Zone to create a Certificate
        hosted_zone = HostedZone.from_lookup(
            self,
            id = "website_hosted_zone",
            domain_name = DOMAIN_NAME
        )

        cert = Certificate(
            self,
            id = "website_certificate",
            domain_name = DOMAIN_NAME,
            subject_alternative_names = [f"www.{DOMAIN_NAME}"],
            validation = CertificateValidation.from_dns(hosted_zone)
        )

        # Now we set up everything for the CloudFront distribution

        # Note: Looks like OAI might be depreciated at some point in favor of
        # Origin Access Control...but I'm not sure OAC is a Python CDK
        # "first class citizen" yet?
        oai = OriginAccessIdentity(self, "origin_access_identity")
        oai.apply_removal_policy(RemovalPolicy.DESTROY)
       
        # Note: We use the OAI for bucket access to...force HTTPS IIRC?
        website_bucket.grant_read(identity=oai)

        domains = [DOMAIN_NAME, f"www.{DOMAIN_NAME}"]

        distribution = Distribution(
            self,
            id = "website_distribution",
            default_root_object = "index.html",
            default_behavior=BehaviorOptions(
                origin = S3Origin(website_bucket, origin_access_identity = oai),
                viewer_protocol_policy=ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
            ),
            domain_names = domains,
            certificate = cert,
        )

        CfnOutput(
            self,
            id = "distribution_url",
            value = distribution.domain_name,
            export_name = f"DistributionDomainName-{DOMAIN_NAME.replace('.', '-')}",
            description = "Static site domain name"
        )

        CfnOutput(
            self,
            id = "bucket_arn",
            value = website_bucket.bucket_arn,
            export_name = f"WebsiteBucketARN-{DOMAIN_NAME.replace('.', '-')}",
            description = "Static site bucket name"
        )

def arn_s3(bucket, key=None):
    if key:
        return f"arn:localaws:s3:::{bucket}/{key}"
    return f"arn:localaws:s3:::{bucket}"


def arn_dynamodb(table=None):
    if table:
        return f"arn:localaws:dynamodb:::table/{table}"
    return "arn:localaws:dynamodb:::table/*"


def arn_ec2(instance_id=None):
    if instance_id:
        return f"arn:localaws:ec2:::instance/{instance_id}"
    return "arn:localaws:ec2:::instance/*"


def arn_lambda(name=None):
    if name:
        return f"arn:localaws:lambda:::function/{name}"
    return "arn:localaws:lambda:::function/*"

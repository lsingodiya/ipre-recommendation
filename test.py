from sagemaker.processing import ScriptProcessor
import sagemaker

session = sagemaker.Session()
role = sagemaker.get_execution_role()

image_uri = sagemaker.image_uris.retrieve(
    framework="sklearn",
    region=session.boto_region_name,
    version="1.2-1"
)

processor = ScriptProcessor(
    image_uri=image_uri,
    command=["python3"],
    role=role,
    instance_type="ml.t3.medium",
    instance_count=1
)

processor.run(code="scripts/market_basket.py")
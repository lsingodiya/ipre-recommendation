import sagemaker
from sagemaker.workflow.pipeline import Pipeline
from sagemaker.workflow.steps import ProcessingStep
from sagemaker.processing import ScriptProcessor

session = sagemaker.session.Session()
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
    instance_type="ml.t3.xlarge",
    instance_count=1
)


def step(name, script, depends=None):
    return ProcessingStep(
        name=name,
        processor=processor,
        code=f"scripts/{script}",
        depends_on=depends or []
    )


# --------------------------------------------------
# SIMPLE + STABLE PIPELINE (NO PROPERTY REFERENCES)
# --------------------------------------------------

market_basket = step("MarketBasket", "market_basket.py")

clustering = step(
    "Clustering",
    "clustering.py",
    depends=["MarketBasket"]
)

associations = step(
    "Associations",
    "associations.py",
    depends=["Clustering"]
)

ranking = step(
    "Ranking",
    "ranking.py",
    depends=["Associations"]
)

feedback = step(
    "FeedbackCalibration",
    "feedback.py",
    depends=["Ranking"]
)


pipeline = Pipeline(
    name="ipre-recommendation-prod",
    steps=[
        market_basket,
        clustering,
        associations,
        ranking,
        feedback
    ],
    sagemaker_session=session
)


if __name__ == "__main__":
    pipeline.upsert(role_arn=role)
    execution = pipeline.start()
    print("Pipeline started:", execution.arn)
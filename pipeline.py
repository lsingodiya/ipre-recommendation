"""
pipeline.py — IPRE SageMaker Pipeline (6 steps)

Execution order:
  1. MarketBasket        ProcessingStep  — builds market_basket.csv
  2. ClusteringTrain     TrainingStep    — trains KMeans, saves model.tar.gz
  3. ClusteringRegister  ModelStep       — registers model in Model Registry
  4. Associations        ProcessingStep  — mines association rules per cluster
  5. Ranking             ProcessingStep  — scores + ranks recommendations
  6. FeedbackCalibration ProcessingStep  — applies feedback, publishes final CSV

Endpoint deployment is handled by deploy_endpoint.py (run separately after
the pipeline completes). EndpointConfigStep / EndpointStep were removed
because they are not available in all SageMaker SDK versions and endpoint
deployment is better kept separate from the data pipeline.
"""

import sagemaker
from sagemaker.sklearn.estimator import SKLearn
from sagemaker.workflow.pipeline import Pipeline
from sagemaker.workflow.steps import ProcessingStep, TrainingStep
from sagemaker.workflow.model_step import ModelStep
from sagemaker.workflow.parameters import ParameterString
from sagemaker.workflow.pipeline_context import PipelineSession
from sagemaker.processing import ScriptProcessor, ProcessingInput, ProcessingOutput
from sagemaker.model import Model

# --------------------------------------------------
# Session
# PipelineSession resolves step output properties lazily — do not swap for a
# regular Session or downstream step property references won't resolve.
# --------------------------------------------------
pipeline_session = PipelineSession()
role             = sagemaker.get_execution_role()
region           = pipeline_session.boto_region_name
bucket           = "ipre-prod-poc"

sklearn_image = sagemaker.image_uris.retrieve(
    framework="sklearn",
    region=region,
    version="1.2-1",
)


def make_processor(instance_type: str = "ml.t3.xlarge") -> ScriptProcessor:
    """Each step gets its own ScriptProcessor — independent instance type control."""
    return ScriptProcessor(
        image_uri=sklearn_image,
        command=["python3"],
        role=role,
        instance_type=instance_type,
        instance_count=1,
        sagemaker_session=pipeline_session,
    )


# ==============================================================
# PIPELINE PARAMETERS
# ==============================================================

customers_input = ParameterString(
    name="InputCustomers",
    default_value=f"s3://{bucket}/raw/customers/customer.csv",
)
products_input = ParameterString(
    name="InputProducts",
    default_value=f"s3://{bucket}/raw/products/product.csv",
)
invoices_input = ParameterString(
    name="InputInvoices",
    default_value=f"s3://{bucket}/raw/invoices/invoice.csv",
)
model_approval_status = ParameterString(
    name="ModelApprovalStatus",
    default_value="Approved",
    # Set to "PendingManualApproval" to require a human review gate in
    # Model Registry before deploy_endpoint.py will deploy the new version.
)

# NOTE: feedback is NOT a pipeline parameter or ProcessingInput.
# SageMaker validates all ProcessingInput S3 paths at job creation time and
# raises ClientError if the object is missing — crashing the pipeline before
# any code runs. feedback.py reads the feedback CSV from S3 via boto3 at
# runtime where a missing file is handled gracefully.


# ==============================================================
# STEP 1 — MARKET BASKET
# ==============================================================

market_basket = ProcessingStep(
    name="MarketBasket",
    processor=make_processor(),
    code="scripts/market_basket.py",
    inputs=[
        ProcessingInput(source=customers_input, destination="/opt/ml/processing/input/customers"),
        ProcessingInput(source=products_input,  destination="/opt/ml/processing/input/products"),
        ProcessingInput(source=invoices_input,  destination="/opt/ml/processing/input/invoices"),
    ],
    outputs=[
        ProcessingOutput(output_name="output", source="/opt/ml/processing/output"),
    ],
)


# ==============================================================
# STEP 2 — CLUSTERING TRAINING JOB
#
# Trains one KMeans + StandardScaler per segment.
# Writes two outputs:
#   /opt/ml/model/       → model.tar.gz (KMeans pickles + model_registry.json)
#   /opt/ml/output/data/ → customer_clusters.csv (consumed by steps 4 and 5)
# ==============================================================

clustering_estimator = SKLearn(
    entry_point="scripts/train_clustering.py",
    framework_version="1.2-1",
    instance_type="ml.m5.xlarge",
    instance_count=1,
    role=role,
    sagemaker_session=pipeline_session,
    output_path=f"s3://{bucket}/models/clustering",
    base_job_name="ipre-clustering",
)

clustering_train = TrainingStep(
    name="ClusteringTrain",
    estimator=clustering_estimator,
    inputs={
        "market_basket": sagemaker.inputs.TrainingInput(
            s3_data=market_basket.properties.ProcessingOutputConfig.Outputs["output"].S3Output.S3Uri,
            content_type="text/csv",
        )
    },
    depends_on=[market_basket],
)


# ==============================================================
# STEP 3 — REGISTER MODEL IN MODEL REGISTRY
#
# Registers model.tar.gz into 'ipre-clustering-models' Model Package Group.
# Every pipeline run creates a new versioned entry — enabling rollback,
# A/B comparison, and full audit trail in SageMaker Studio.
# deploy_endpoint.py reads the latest approved version from here.
# ==============================================================

clustering_model = Model(
    image_uri=sklearn_image,
    model_data=clustering_train.properties.ModelArtifacts.S3ModelArtifacts,
    role=role,
    sagemaker_session=pipeline_session,
    entry_point="scripts/inference.py",
    env={
        "RECO_BUCKET": bucket,
        "RECO_KEY":    "final/recommendations.csv",
    },
)

register_model = ModelStep(
    name="ClusteringRegister",
    step_args=clustering_model.register(
        content_types=["application/json"],
        response_types=["application/json"],
        inference_instances=["ml.m5.large", "ml.m5.xlarge"],
        transform_instances=["ml.m5.xlarge"],
        model_package_group_name="ipre-clustering-models",
        approval_status=model_approval_status,
        description="IPRE KMeans clustering — segments customers by purchase behavior",
    ),
    depends_on=[clustering_train],
)


# ==============================================================
# STEP 4 — ASSOCIATIONS
#
# Reads raw invoices to reconstruct basket sessions (window-based basket_id)
# so invoices_input is mounted here as well as in MarketBasket.
# FIX: Clustering input now uses ModelArtifacts.S3ModelArtifacts (model.tar.gz)
# because customer_clusters.csv is written to /opt/ml/model/ in
# train_clustering.py, making it part of model.tar.gz. OutputDataConfig.S3OutputPath
# points to a separate output.tar.gz that Processing containers can't reliably
# find when multiple tar files exist in the same S3 prefix.
# ==============================================================

associations = ProcessingStep(
    name="Associations",
    processor=make_processor("ml.m5.xlarge"),
    code="scripts/associations.py",
    inputs=[
        ProcessingInput(
            source=market_basket.properties.ProcessingOutputConfig.Outputs["output"].S3Output.S3Uri,
            destination="/opt/ml/processing/input/market_basket",
        ),
        ProcessingInput(
            source=clustering_train.properties.ModelArtifacts.S3ModelArtifacts,
            destination="/opt/ml/processing/input/clustering",
        ),
        ProcessingInput(
            source=invoices_input,
            destination="/opt/ml/processing/input/invoices",
        ),
    ],
    outputs=[
        ProcessingOutput(output_name="output", source="/opt/ml/processing/output"),
    ],
    depends_on=[market_basket, clustering_train],
)


# ==============================================================
# STEP 5 — RANKING
# ==============================================================

ranking = ProcessingStep(
    name="Ranking",
    processor=make_processor(),
    code="scripts/ranking.py",
    inputs=[
        ProcessingInput(
            source=market_basket.properties.ProcessingOutputConfig.Outputs["output"].S3Output.S3Uri,
            destination="/opt/ml/processing/input/market_basket",
        ),
        ProcessingInput(
            source=clustering_train.properties.ModelArtifacts.S3ModelArtifacts,
            destination="/opt/ml/processing/input/clustering",
        ),
        ProcessingInput(
            source=associations.properties.ProcessingOutputConfig.Outputs["output"].S3Output.S3Uri,
            destination="/opt/ml/processing/input/associations",
        ),
    ],
    outputs=[
        ProcessingOutput(output_name="output", source="/opt/ml/processing/output"),
    ],
    depends_on=[market_basket, clustering_train, associations],
)


# ==============================================================
# STEP 6 — FEEDBACK CALIBRATION
# No feedback ProcessingInput — feedback.py reads from S3 via boto3 at runtime.
# ==============================================================

feedback = ProcessingStep(
    name="FeedbackCalibration",
    processor=make_processor(),
    code="scripts/feedback.py",
    inputs=[
        ProcessingInput(
            source=ranking.properties.ProcessingOutputConfig.Outputs["output"].S3Output.S3Uri,
            destination="/opt/ml/processing/input/ranking",
        ),
    ],
    outputs=[
        ProcessingOutput(output_name="output", source="/opt/ml/processing/output"),
    ],
    depends_on=[ranking],
)


# ==============================================================
# BUILD PIPELINE
# ==============================================================

pipeline = Pipeline(
    name="ipre-prod-poc",
    parameters=[
        customers_input,
        products_input,
        invoices_input,
        model_approval_status,
    ],
    steps=[
        market_basket,
        clustering_train,
        register_model,
        associations,
        ranking,
        feedback,
    ],
    sagemaker_session=pipeline_session,
)


if __name__ == "__main__":
    pipeline.upsert(role_arn=role)
    print("Pipeline registered. Starting execution...")
    execution = pipeline.start()
    print(f"Pipeline started: {execution.arn}")
    print("Monitor at: SageMaker Studio → Pipelines → ipre-prod-poc")

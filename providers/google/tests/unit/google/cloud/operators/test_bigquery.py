#
# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
from __future__ import annotations

import json
import logging
import os
from contextlib import suppress
from unittest import mock
from unittest.mock import ANY, MagicMock

import pandas as pd
import pytest
from google.cloud.bigquery import DEFAULT_RETRY, ScalarQueryParameter, Table
from google.cloud.exceptions import Conflict

from airflow.exceptions import (
    AirflowException,
    AirflowSkipException,
    AirflowTaskTimeout,
    TaskDeferred,
)
from airflow.providers.common.compat.openlineage.facet import (
    DocumentationDatasetFacet,
    ErrorMessageRunFacet,
    ExternalQueryRunFacet,
    InputDataset,
    LifecycleStateChange,
    LifecycleStateChangeDatasetFacet,
    PreviousIdentifier,
    SchemaDatasetFacet,
    SchemaDatasetFacetFields,
    SQLJobFacet,
)
from airflow.providers.google.cloud.openlineage.utils import BIGQUERY_NAMESPACE
from airflow.providers.google.cloud.operators.bigquery import (
    BigQueryCheckOperator,
    BigQueryColumnCheckOperator,
    BigQueryCreateEmptyDatasetOperator,
    BigQueryCreateTableOperator,
    BigQueryDeleteDatasetOperator,
    BigQueryDeleteTableOperator,
    BigQueryGetDataOperator,
    BigQueryGetDatasetOperator,
    BigQueryGetDatasetTablesOperator,
    BigQueryInsertJobOperator,
    BigQueryIntervalCheckOperator,
    BigQueryTableCheckOperator,
    BigQueryUpdateDatasetOperator,
    BigQueryUpdateTableOperator,
    BigQueryUpdateTableSchemaOperator,
    BigQueryUpsertTableOperator,
    BigQueryValueCheckOperator,
)
from airflow.providers.google.cloud.triggers.bigquery import (
    BigQueryCheckTrigger,
    BigQueryGetDataTrigger,
    BigQueryInsertJobTrigger,
    BigQueryIntervalCheckTrigger,
    BigQueryValueCheckTrigger,
)
from airflow.utils.task_group import TaskGroup
from airflow.utils.timezone import datetime

TASK_ID = "test-bq-generic-operator"
TEST_DATASET = "test-dataset"
TEST_DATASET_LOCATION = "EU"
TEST_GCP_PROJECT_ID = "test-project"
TEST_JOB_PROJECT_ID = "test-job-project"
TEST_DELETE_CONTENTS = True
TEST_TABLE_ID = "test-table-id"
TEST_JOB_ID = "test-job-id"
TEST_GCS_BUCKET = "test-bucket"
TEST_GCS_CSV_DATA = ["dir1/*.csv"]
TEST_SOURCE_CSV_FORMAT = "CSV"
TEST_GCS_PARQUET_DATA = ["dir1/*.parquet"]
TEST_SOURCE_PARQUET_FORMAT = "PARQUET"
DEFAULT_DATE = datetime(2015, 1, 1)
TEST_DAG_ID = "test-bigquery-operators"
TEST_TABLE_RESOURCES = {"tableReference": {"tableId": TEST_TABLE_ID}, "expirationTime": 1234567}
VIEW_DEFINITION = {
    "query": f"SELECT * FROM `{TEST_DATASET}.{TEST_TABLE_ID}`",
    "useLegacySql": False,
}
MATERIALIZED_VIEW_DEFINITION = {
    "query": f"SELECT product, SUM(amount) FROM `{TEST_DATASET}.{TEST_TABLE_ID}` GROUP BY product",
    "enableRefresh": True,
    "refreshIntervalMs": 2000000,
}
TEST_TABLE = "test-table"
GCP_CONN_ID = "google_cloud_default"
TEST_JOB_ID_1 = "test-job-id"
TEST_JOB_ID_2 = "test-123"
TEST_FULL_JOB_ID = f"{TEST_GCP_PROJECT_ID}:{TEST_DATASET_LOCATION}:{TEST_JOB_ID_1}"
TEST_FULL_JOB_ID_2 = f"{TEST_GCP_PROJECT_ID}:{TEST_DATASET_LOCATION}:{TEST_JOB_ID_2}"


def create_bigquery_job(errors=None, error_result=None, state="DONE"):
    mock_job = MagicMock()
    mock_job.errors = errors or []
    mock_job.error_result = error_result
    mock_job.state = state
    mock_job.job_id = "mock-job-id"
    return mock_job


def assert_warning(msg: str, warnings):
    assert any(msg in str(w) for w in warnings)


class TestBigQueryCreateTableOperator:
    @mock.patch("airflow.providers.google.cloud.operators.bigquery.BigQueryHook")
    def test_execute(self, mock_hook):
        operator = BigQueryCreateTableOperator(
            task_id=TASK_ID,
            dataset_id=TEST_DATASET,
            project_id=TEST_GCP_PROJECT_ID,
            table_id=TEST_TABLE_ID,
            table_resource={},
        )

        operator.execute(context=MagicMock())

        mock_hook.return_value.create_table.assert_called_once_with(
            dataset_id=TEST_DATASET,
            project_id=TEST_GCP_PROJECT_ID,
            table_id=TEST_TABLE_ID,
            table_resource={},
            exists_ok=False,
            schema_fields=None,
            location=None,
            timeout=None,
        )

    @mock.patch("airflow.providers.google.cloud.operators.bigquery.BigQueryHook")
    def test_create_view(self, mock_hook):
        body = {
            "tableReference": {
                "tableId": TEST_TABLE_ID,
                "projectId": TEST_GCP_PROJECT_ID,
                "datasetId": TEST_DATASET,
            },
            "view": VIEW_DEFINITION,
        }
        operator = BigQueryCreateTableOperator(
            task_id=TASK_ID,
            dataset_id=TEST_DATASET,
            project_id=TEST_GCP_PROJECT_ID,
            table_id=TEST_TABLE_ID,
            table_resource=body,
        )
        operator.execute(context=MagicMock())

    @mock.patch("airflow.providers.google.cloud.operators.bigquery.BigQueryHook")
    def test_create_materialized_view(self, mock_hook):
        body = {
            "tableReference": {
                "tableId": TEST_TABLE_ID,
                "projectId": TEST_GCP_PROJECT_ID,
                "datasetId": TEST_DATASET,
            },
            "materializedView": MATERIALIZED_VIEW_DEFINITION,
        }
        operator = BigQueryCreateTableOperator(
            task_id=TASK_ID,
            dataset_id=TEST_DATASET,
            project_id=TEST_GCP_PROJECT_ID,
            table_id=TEST_TABLE_ID,
            table_resource=body,
        )

        operator.execute(context=MagicMock())

        mock_hook.return_value.create_table.assert_called_once_with(
            dataset_id=TEST_DATASET,
            project_id=TEST_GCP_PROJECT_ID,
            table_id=TEST_TABLE_ID,
            schema_fields=None,
            table_resource=body,
            exists_ok=False,
            location=None,
            timeout=None,
        )

    @mock.patch("airflow.providers.google.cloud.operators.bigquery.BigQueryHook")
    def test_create_clustered_table(self, mock_hook):
        schema_fields = [
            {"name": "emp_name", "type": "STRING", "mode": "REQUIRED"},
            {"name": "date_hired", "type": "DATE", "mode": "REQUIRED"},
            {"name": "date_birth", "type": "DATE", "mode": "NULLABLE"},
        ]
        time_partitioning = {"type": "DAY", "field": "date_hired"}
        cluster_fields = ["date_birth"]
        body = {
            "tableReference": {
                "tableId": TEST_TABLE_ID,
                "projectId": TEST_GCP_PROJECT_ID,
                "datasetId": TEST_DATASET,
            },
            "schema": schema_fields,
            "timePartitioning": time_partitioning,
            "clusterFields": cluster_fields,
        }
        operator = BigQueryCreateTableOperator(
            task_id=TASK_ID,
            dataset_id=TEST_DATASET,
            project_id=TEST_GCP_PROJECT_ID,
            table_id=TEST_TABLE_ID,
            table_resource=body,
        )

        operator.execute(context=MagicMock())

        mock_hook.return_value.create_table.assert_called_once_with(
            dataset_id=TEST_DATASET,
            project_id=TEST_GCP_PROJECT_ID,
            table_id=TEST_TABLE_ID,
            table_resource=body,
            exists_ok=False,
            schema_fields=None,
            timeout=None,
            location=None,
        )

    @pytest.mark.parametrize(
        "if_exists, is_conflict, expected_error, log_msg",
        [
            ("ignore", False, None, None),
            ("log", False, None, None),
            ("log", True, None, f"Table {TEST_DATASET}.{TEST_TABLE_ID} already exists."),
            ("fail", False, None, None),
            ("fail", True, AirflowException, None),
            ("skip", False, None, None),
            ("skip", True, AirflowSkipException, None),
        ],
    )
    @mock.patch("airflow.providers.google.cloud.operators.bigquery.BigQueryHook")
    def test_create_existing_table(self, mock_hook, caplog, if_exists, is_conflict, expected_error, log_msg):
        body = {
            "tableReference": {
                "tableId": TEST_TABLE_ID,
                "projectId": TEST_GCP_PROJECT_ID,
                "datasetId": TEST_DATASET,
            },
            "view": VIEW_DEFINITION,
        }
        operator = BigQueryCreateTableOperator(
            task_id=TASK_ID,
            dataset_id=TEST_DATASET,
            project_id=TEST_GCP_PROJECT_ID,
            table_id=TEST_TABLE_ID,
            table_resource=body,
            if_exists=if_exists,
        )
        if is_conflict:
            mock_hook.return_value.create_table.side_effect = Conflict("any")
        else:
            mock_hook.return_value.create_table.side_effect = None
            if expected_error is not None:
                with pytest.raises(expected_error):
                    operator.execute(context=MagicMock())
            else:
                operator.execute(context=MagicMock())
            if log_msg is not None:
                assert log_msg in caplog.text

    @mock.patch("airflow.providers.google.cloud.operators.bigquery.BigQueryHook")
    def test_get_openlineage_facets_on_complete(self, mock_hook):
        schema_fields = [
            {"name": "field1", "type": "STRING", "description": "field1 description"},
            {"name": "field2", "type": "INTEGER"},
        ]
        table_resource = {
            "tableReference": {
                "projectId": TEST_GCP_PROJECT_ID,
                "datasetId": TEST_DATASET,
                "tableId": TEST_TABLE_ID,
            },
            "description": "Table description.",
            "schema": {"fields": schema_fields},
        }
        mock_hook.return_value.create_table.return_value = Table.from_api_repr(table_resource)
        operator = BigQueryCreateTableOperator(
            task_id=TASK_ID,
            dataset_id=TEST_DATASET,
            project_id=TEST_GCP_PROJECT_ID,
            table_id=TEST_TABLE_ID,
            table_resource=table_resource,
        )

        operator.execute(context=MagicMock())

        mock_hook.return_value.create_table.assert_called_once_with(
            dataset_id=TEST_DATASET,
            project_id=TEST_GCP_PROJECT_ID,
            table_id=TEST_TABLE_ID,
            table_resource=table_resource,
            exists_ok=False,
            schema_fields=None,
            location=None,
            timeout=None,
        )

        result = operator.get_openlineage_facets_on_complete(None)
        assert not result.run_facets
        assert not result.job_facets
        assert not result.inputs
        assert len(result.outputs) == 1
        assert result.outputs[0].namespace == BIGQUERY_NAMESPACE
        assert result.outputs[0].name == f"{TEST_GCP_PROJECT_ID}.{TEST_DATASET}.{TEST_TABLE_ID}"
        assert result.outputs[0].facets == {
            "schema": SchemaDatasetFacet(
                fields=[
                    SchemaDatasetFacetFields(name="field1", type="STRING", description="field1 description"),
                    SchemaDatasetFacetFields(name="field2", type="INTEGER"),
                ]
            ),
            "documentation": DocumentationDatasetFacet(description="Table description."),
        }


class TestBigQueryDeleteDatasetOperator:
    @mock.patch("airflow.providers.google.cloud.operators.bigquery.BigQueryHook")
    def test_execute(self, mock_hook):
        operator = BigQueryDeleteDatasetOperator(
            task_id=TASK_ID,
            dataset_id=TEST_DATASET,
            project_id=TEST_GCP_PROJECT_ID,
            delete_contents=TEST_DELETE_CONTENTS,
        )

        operator.execute(None)
        mock_hook.return_value.delete_dataset.assert_called_once_with(
            dataset_id=TEST_DATASET, project_id=TEST_GCP_PROJECT_ID, delete_contents=TEST_DELETE_CONTENTS
        )


class TestBigQueryCreateEmptyDatasetOperator:
    @mock.patch("airflow.providers.google.cloud.operators.bigquery.BigQueryHook")
    def test_execute(self, mock_hook):
        operator = BigQueryCreateEmptyDatasetOperator(
            task_id=TASK_ID,
            dataset_id=TEST_DATASET,
            project_id=TEST_GCP_PROJECT_ID,
            location=TEST_DATASET_LOCATION,
        )

        operator.execute(context=MagicMock())
        mock_hook.return_value.create_empty_dataset.assert_called_once_with(
            dataset_id=TEST_DATASET,
            project_id=TEST_GCP_PROJECT_ID,
            location=TEST_DATASET_LOCATION,
            dataset_reference={},
            exists_ok=False,
        )

    @pytest.mark.parametrize(
        "if_exists, is_conflict, expected_error, log_msg",
        [
            ("ignore", False, None, None),
            ("log", False, None, None),
            ("log", True, None, f"Dataset {TEST_DATASET} already exists."),
            ("fail", False, None, None),
            ("fail", True, AirflowException, None),
            ("skip", False, None, None),
            ("skip", True, AirflowSkipException, None),
        ],
    )
    @mock.patch("airflow.providers.google.cloud.operators.bigquery.BigQueryHook")
    def test_create_empty_dataset(self, mock_hook, caplog, if_exists, is_conflict, expected_error, log_msg):
        operator = BigQueryCreateEmptyDatasetOperator(
            task_id=TASK_ID,
            dataset_id=TEST_DATASET,
            project_id=TEST_GCP_PROJECT_ID,
            location=TEST_DATASET_LOCATION,
            if_exists=if_exists,
        )
        if is_conflict:
            mock_hook.return_value.create_empty_dataset.side_effect = Conflict("any")
        else:
            mock_hook.return_value.create_empty_dataset.side_effect = None
        if expected_error is not None:
            with pytest.raises(expected_error):
                operator.execute(context=MagicMock())
        else:
            operator.execute(context=MagicMock())
        if log_msg is not None:
            assert log_msg in caplog.text


class TestBigQueryGetDatasetOperator:
    @mock.patch("airflow.providers.google.cloud.operators.bigquery.BigQueryHook")
    def test_execute(self, mock_hook):
        operator = BigQueryGetDatasetOperator(
            task_id=TASK_ID, dataset_id=TEST_DATASET, project_id=TEST_GCP_PROJECT_ID
        )

        operator.execute(context=MagicMock())
        mock_hook.return_value.get_dataset.assert_called_once_with(
            dataset_id=TEST_DATASET, project_id=TEST_GCP_PROJECT_ID
        )


class TestBigQueryUpdateTableOperator:
    @mock.patch("airflow.providers.google.cloud.operators.bigquery.BigQueryHook")
    def test_execute(self, mock_hook):
        table_resource = {"friendlyName": "Test TB"}
        operator = BigQueryUpdateTableOperator(
            table_resource=table_resource,
            task_id=TASK_ID,
            dataset_id=TEST_DATASET,
            table_id=TEST_TABLE_ID,
            project_id=TEST_GCP_PROJECT_ID,
        )

        operator.execute(context=MagicMock())
        mock_hook.return_value.update_table.assert_called_once_with(
            table_resource=table_resource,
            fields=None,
            dataset_id=TEST_DATASET,
            table_id=TEST_TABLE_ID,
            project_id=TEST_GCP_PROJECT_ID,
        )

    @mock.patch("airflow.providers.google.cloud.operators.bigquery.BigQueryHook")
    def test_get_openlineage_facets_on_complete(self, mock_hook):
        table_resource = {
            "tableReference": {
                "projectId": TEST_GCP_PROJECT_ID,
                "datasetId": TEST_DATASET,
                "tableId": TEST_TABLE_ID,
            },
            "description": "Table description.",
            "schema": {
                "fields": [
                    {"name": "field1", "type": "STRING", "description": "field1 description"},
                    {"name": "field2", "type": "INTEGER"},
                ]
            },
        }
        mock_hook.return_value.update_table.return_value = table_resource
        operator = BigQueryUpdateTableOperator(
            table_resource={},
            task_id=TASK_ID,
            dataset_id=TEST_DATASET,
            table_id=TEST_TABLE_ID,
            project_id=TEST_GCP_PROJECT_ID,
        )

        operator.execute(context=MagicMock())
        result = operator.get_openlineage_facets_on_complete(None)
        assert not result.run_facets
        assert not result.job_facets
        assert not result.inputs
        assert len(result.outputs) == 1
        assert result.outputs[0].namespace == BIGQUERY_NAMESPACE
        assert result.outputs[0].name == f"{TEST_GCP_PROJECT_ID}.{TEST_DATASET}.{TEST_TABLE_ID}"
        assert result.outputs[0].facets == {
            "schema": SchemaDatasetFacet(
                fields=[
                    SchemaDatasetFacetFields(name="field1", type="STRING", description="field1 description"),
                    SchemaDatasetFacetFields(name="field2", type="INTEGER"),
                ]
            ),
            "documentation": DocumentationDatasetFacet(description="Table description."),
        }


class TestBigQueryUpdateTableSchemaOperator:
    @mock.patch("airflow.providers.google.cloud.operators.bigquery.BigQueryHook")
    def test_execute(self, mock_hook):
        schema_field_updates = [
            {
                "name": "emp_name",
                "description": "Name of employee",
            }
        ]

        operator = BigQueryUpdateTableSchemaOperator(
            schema_fields_updates=schema_field_updates,
            include_policy_tags=False,
            task_id=TASK_ID,
            dataset_id=TEST_DATASET,
            table_id=TEST_TABLE_ID,
            project_id=TEST_GCP_PROJECT_ID,
            location=TEST_DATASET_LOCATION,
            impersonation_chain=["service-account@myproject.iam.gserviceaccount.com"],
        )
        operator.execute(context=MagicMock())

        mock_hook.assert_called_once_with(
            gcp_conn_id=GCP_CONN_ID,
            impersonation_chain=["service-account@myproject.iam.gserviceaccount.com"],
            location=TEST_DATASET_LOCATION,
        )
        mock_hook.return_value.update_table_schema.assert_called_once_with(
            schema_fields_updates=schema_field_updates,
            include_policy_tags=False,
            dataset_id=TEST_DATASET,
            table_id=TEST_TABLE_ID,
            project_id=TEST_GCP_PROJECT_ID,
        )

    @mock.patch("airflow.providers.google.cloud.operators.bigquery.BigQueryHook")
    def test_get_openlineage_facets_on_complete(self, mock_hook):
        table_resource = {
            "tableReference": {
                "projectId": TEST_GCP_PROJECT_ID,
                "datasetId": TEST_DATASET,
                "tableId": TEST_TABLE_ID,
            },
            "description": "Table description.",
            "schema": {
                "fields": [
                    {"name": "field1", "type": "STRING", "description": "field1 description"},
                    {"name": "field2", "type": "INTEGER"},
                ]
            },
        }
        mock_hook.return_value.update_table_schema.return_value = table_resource
        schema_field_updates = [
            {
                "name": "emp_name",
                "description": "Name of employee",
            }
        ]

        operator = BigQueryUpdateTableSchemaOperator(
            schema_fields_updates=schema_field_updates,
            include_policy_tags=False,
            task_id=TASK_ID,
            dataset_id=TEST_DATASET,
            table_id=TEST_TABLE_ID,
            project_id=TEST_GCP_PROJECT_ID,
            location=TEST_DATASET_LOCATION,
            impersonation_chain=["service-account@myproject.iam.gserviceaccount.com"],
        )
        operator.execute(context=MagicMock())

        result = operator.get_openlineage_facets_on_complete(None)
        assert not result.run_facets
        assert not result.job_facets
        assert not result.inputs
        assert len(result.outputs) == 1
        assert result.outputs[0].namespace == BIGQUERY_NAMESPACE
        assert result.outputs[0].name == f"{TEST_GCP_PROJECT_ID}.{TEST_DATASET}.{TEST_TABLE_ID}"
        assert result.outputs[0].facets == {
            "schema": SchemaDatasetFacet(
                fields=[
                    SchemaDatasetFacetFields(name="field1", type="STRING", description="field1 description"),
                    SchemaDatasetFacetFields(name="field2", type="INTEGER"),
                ]
            ),
            "documentation": DocumentationDatasetFacet(description="Table description."),
        }


class TestBigQueryUpdateDatasetOperator:
    @mock.patch("airflow.providers.google.cloud.operators.bigquery.BigQueryHook")
    def test_execute(self, mock_hook):
        dataset_resource = {"friendlyName": "Test DS"}
        operator = BigQueryUpdateDatasetOperator(
            dataset_resource=dataset_resource,
            task_id=TASK_ID,
            dataset_id=TEST_DATASET,
            project_id=TEST_GCP_PROJECT_ID,
        )

        operator.execute(context=MagicMock())
        mock_hook.return_value.update_dataset.assert_called_once_with(
            dataset_resource=dataset_resource,
            dataset_id=TEST_DATASET,
            project_id=TEST_GCP_PROJECT_ID,
            fields=list(dataset_resource.keys()),
        )


class TestBigQueryGetDataOperator:
    @pytest.mark.parametrize("as_dict", [True, False])
    @mock.patch("airflow.providers.google.cloud.operators.bigquery.BigQueryHook")
    def test_execute__table(self, mock_hook, as_dict):
        max_results = 100
        selected_fields = "DATE"
        operator = BigQueryGetDataOperator(
            gcp_conn_id=GCP_CONN_ID,
            task_id=TASK_ID,
            dataset_id=TEST_DATASET,
            table_id=TEST_TABLE_ID,
            table_project_id=TEST_GCP_PROJECT_ID,
            max_results=max_results,
            selected_fields=selected_fields,
            location=TEST_DATASET_LOCATION,
            as_dict=as_dict,
            use_legacy_sql=False,
        )
        operator.execute(None)
        mock_hook.assert_called_with(gcp_conn_id=GCP_CONN_ID, impersonation_chain=None, use_legacy_sql=False)
        mock_hook.return_value.list_rows.assert_called_once_with(
            dataset_id=TEST_DATASET,
            table_id=TEST_TABLE_ID,
            project_id=TEST_GCP_PROJECT_ID,
            max_results=max_results,
            selected_fields=selected_fields,
            location=TEST_DATASET_LOCATION,
        )

    @pytest.mark.parametrize("as_dict", [True, False])
    @mock.patch("airflow.providers.google.cloud.operators.bigquery.BigQueryHook")
    def test_execute__job_id(self, mock_hook, as_dict):
        max_results = 100
        selected_fields = "DATE"
        operator = BigQueryGetDataOperator(
            job_project_id=TEST_JOB_PROJECT_ID,
            gcp_conn_id=GCP_CONN_ID,
            task_id=TASK_ID,
            job_id=TEST_JOB_ID,
            max_results=max_results,
            selected_fields=selected_fields,
            location=TEST_DATASET_LOCATION,
            as_dict=as_dict,
        )
        operator.execute(None)
        mock_hook.return_value.get_query_results.assert_called_once_with(
            job_id=TEST_JOB_ID,
            location=TEST_DATASET_LOCATION,
            max_results=max_results,
            project_id=TEST_JOB_PROJECT_ID,
            selected_fields=selected_fields,
        )

    @mock.patch("airflow.providers.google.cloud.operators.bigquery.BigQueryHook")
    def test_execute__job_id_table_id_mutual_exclusive_exception(self, _):
        max_results = 100
        selected_fields = "DATE"
        operator = BigQueryGetDataOperator(
            gcp_conn_id=GCP_CONN_ID,
            task_id=TASK_ID,
            dataset_id=TEST_DATASET,
            table_id=TEST_TABLE_ID,
            table_project_id=TEST_GCP_PROJECT_ID,
            job_id=TEST_JOB_ID,
            max_results=max_results,
            selected_fields=selected_fields,
            location=TEST_DATASET_LOCATION,
        )
        with pytest.raises(AirflowException, match="mutually exclusive"):
            operator.execute(None)

    @mock.patch("airflow.providers.google.cloud.operators.bigquery.BigQueryHook")
    def test_generate_query__with_table_project_id(self, mock_hook):
        operator = BigQueryGetDataOperator(
            gcp_conn_id=GCP_CONN_ID,
            task_id=TASK_ID,
            dataset_id=TEST_DATASET,
            table_id=TEST_TABLE_ID,
            table_project_id=TEST_GCP_PROJECT_ID,
            max_results=100,
            use_legacy_sql=False,
        )
        assert (
            operator.generate_query(hook=mock_hook) == f"select * from `{TEST_GCP_PROJECT_ID}."
            f"{TEST_DATASET}.{TEST_TABLE_ID}` limit 100"
        )

    @mock.patch("airflow.providers.google.cloud.operators.bigquery.BigQueryHook")
    def test_generate_query__without_table_project_id(self, mock_hook):
        hook_project_id = mock_hook.project_id
        operator = BigQueryGetDataOperator(
            gcp_conn_id=GCP_CONN_ID,
            task_id=TASK_ID,
            dataset_id=TEST_DATASET,
            table_id=TEST_TABLE_ID,
            max_results=100,
            use_legacy_sql=False,
        )
        assert (
            operator.generate_query(hook=mock_hook) == f"select * from `{hook_project_id}."
            f"{TEST_DATASET}.{TEST_TABLE_ID}` limit 100"
        )

    @pytest.mark.db_test
    @mock.patch("airflow.providers.google.cloud.operators.bigquery.BigQueryHook")
    def test_bigquery_get_data_operator_async_with_selected_fields(
        self, mock_hook, create_task_instance_of_operator
    ):
        """
        Asserts that a task is deferred and a BigQuerygetDataTrigger will be fired
        when the BigQueryGetDataOperator is executed with deferrable=True.
        """
        ti = create_task_instance_of_operator(
            BigQueryGetDataOperator,
            dag_id="dag_id",
            task_id="get_data_from_bq",
            dataset_id=TEST_DATASET,
            table_id=TEST_TABLE_ID,
            job_project_id=TEST_JOB_PROJECT_ID,
            max_results=100,
            selected_fields="value,name",
            deferrable=True,
            use_legacy_sql=False,
        )

        with pytest.raises(TaskDeferred) as exc:
            ti.task.execute(MagicMock())

        assert isinstance(exc.value.trigger, BigQueryGetDataTrigger), (
            "Trigger is not a BigQueryGetDataTrigger"
        )

    @pytest.mark.db_test
    @pytest.mark.parametrize("as_dict", [True, False])
    @mock.patch("airflow.providers.google.cloud.operators.bigquery.BigQueryHook")
    def test_bigquery_get_data_operator_async_without_selected_fields(
        self, mock_hook, create_task_instance_of_operator, as_dict
    ):
        """
        Asserts that a task is deferred and a BigQueryGetDataTrigger will be fired
        when the BigQueryGetDataOperator is executed with deferrable=True.
        """
        ti = create_task_instance_of_operator(
            BigQueryGetDataOperator,
            dag_id="dag_id",
            task_id="get_data_from_bq",
            dataset_id=TEST_DATASET,
            table_id=TEST_TABLE_ID,
            job_project_id=TEST_JOB_PROJECT_ID,
            max_results=100,
            deferrable=True,
            as_dict=as_dict,
            use_legacy_sql=False,
        )

        with pytest.raises(TaskDeferred) as exc:
            ti.task.execute(MagicMock())

        assert isinstance(exc.value.trigger, BigQueryGetDataTrigger), (
            "Trigger is not a BigQueryGetDataTrigger"
        )

    @pytest.mark.parametrize("as_dict", [True, False])
    def test_bigquery_get_data_operator_execute_failure(self, as_dict):
        """Tests that an AirflowException is raised in case of error event"""

        operator = BigQueryGetDataOperator(
            task_id="get_data_from_bq",
            dataset_id=TEST_DATASET,
            table_id="any",
            job_project_id=TEST_JOB_PROJECT_ID,
            max_results=100,
            deferrable=True,
            as_dict=as_dict,
            use_legacy_sql=False,
        )

        with pytest.raises(AirflowException):
            operator.execute_complete(
                context=None, event={"status": "error", "message": "test failure message"}
            )

    @pytest.mark.parametrize("as_dict", [True, False])
    def test_bigquery_get_data_op_execute_complete_with_records(self, as_dict):
        """Asserts that exception is raised with correct expected exception message"""

        operator = BigQueryGetDataOperator(
            task_id="get_data_from_bq",
            dataset_id=TEST_DATASET,
            table_id="any",
            job_project_id=TEST_JOB_PROJECT_ID,
            max_results=100,
            deferrable=True,
            as_dict=as_dict,
            use_legacy_sql=False,
        )

        with mock.patch.object(operator.log, "info") as mock_log_info:
            operator.execute_complete(context=None, event={"status": "success", "records": [20]})
        mock_log_info.assert_called_with("Total extracted rows: %s", 1)

    @pytest.mark.parametrize("as_dict", [True, False])
    @mock.patch("airflow.providers.google.cloud.operators.bigquery.BigQueryHook")
    @mock.patch("airflow.providers.google.cloud.hooks.bigquery.BigQueryJob")
    def test_encryption_configuration(self, mock_job, mock_hook, as_dict):
        encryption_configuration = {
            "kmsKeyName": "projects/PROJECT/locations/LOCATION/keyRings/KEY_RING/cryptoKeys/KEY",
        }

        mock_hook.return_value.insert_job.return_value = mock_job
        mock_hook.return_value.project_id = TEST_GCP_PROJECT_ID

        max_results = 1
        selected_fields = "DATE"
        operator = BigQueryGetDataOperator(
            job_project_id=TEST_GCP_PROJECT_ID,
            gcp_conn_id=GCP_CONN_ID,
            task_id=TASK_ID,
            job_id="",
            max_results=max_results,
            dataset_id=TEST_DATASET,
            table_id=TEST_TABLE_ID,
            selected_fields=selected_fields,
            location=TEST_DATASET_LOCATION,
            as_dict=as_dict,
            encryption_configuration=encryption_configuration,
            deferrable=True,
        )
        with pytest.raises(TaskDeferred):
            operator.execute(MagicMock())
        mock_hook.return_value.insert_job.assert_called_with(
            configuration={
                "query": {
                    "query": f"""select DATE from `{TEST_GCP_PROJECT_ID}.{TEST_DATASET}.{TEST_TABLE_ID}` limit 1""",
                    "useLegacySql": True,
                    "destinationEncryptionConfiguration": encryption_configuration,
                }
            },
            project_id=TEST_GCP_PROJECT_ID,
            location=TEST_DATASET_LOCATION,
            job_id="",
            nowait=True,
        )


class TestBigQueryTableDeleteOperator:
    @mock.patch("airflow.providers.google.cloud.operators.bigquery.BigQueryHook")
    def test_execute(self, mock_hook):
        ignore_if_missing = True
        deletion_dataset_table = f"{TEST_DATASET}.{TEST_TABLE_ID}"

        operator = BigQueryDeleteTableOperator(
            task_id=TASK_ID,
            deletion_dataset_table=deletion_dataset_table,
            ignore_if_missing=ignore_if_missing,
        )

        operator.execute(None)
        mock_hook.return_value.delete_table.assert_called_once_with(
            table_id=deletion_dataset_table, not_found_ok=ignore_if_missing
        )

    @mock.patch("airflow.providers.google.cloud.operators.bigquery.BigQueryHook")
    def test_get_openlineage_facets_on_complete(self, mock_hook):
        mock_hook.return_value.project_id = "default_project_id"
        operator = BigQueryDeleteTableOperator(
            task_id=TASK_ID,
            deletion_dataset_table=f"{TEST_DATASET}.{TEST_TABLE_ID}",
            ignore_if_missing=True,
        )

        operator.execute(None)
        result = operator.get_openlineage_facets_on_complete(None)
        assert not result.run_facets
        assert not result.job_facets
        assert not result.outputs
        assert len(result.inputs) == 1
        assert result.inputs[0].namespace == BIGQUERY_NAMESPACE
        assert result.inputs[0].name == f"default_project_id.{TEST_DATASET}.{TEST_TABLE_ID}"
        assert result.inputs[0].facets == {
            "lifecycleStateChange": LifecycleStateChangeDatasetFacet(
                lifecycleStateChange=LifecycleStateChange.DROP.value,
                previousIdentifier=PreviousIdentifier(
                    namespace=BIGQUERY_NAMESPACE,
                    name=f"default_project_id.{TEST_DATASET}.{TEST_TABLE_ID}",
                ),
            )
        }


class TestBigQueryGetDatasetTablesOperator:
    @mock.patch("airflow.providers.google.cloud.operators.bigquery.BigQueryHook")
    def test_execute(self, mock_hook):
        operator = BigQueryGetDatasetTablesOperator(
            task_id=TASK_ID, dataset_id=TEST_DATASET, project_id=TEST_GCP_PROJECT_ID, max_results=2
        )

        operator.execute(None)
        mock_hook.return_value.get_dataset_tables.assert_called_once_with(
            dataset_id=TEST_DATASET,
            project_id=TEST_GCP_PROJECT_ID,
            max_results=2,
        )


@pytest.mark.parametrize(
    "operator_class, kwargs",
    [
        (BigQueryCheckOperator, dict(sql="Select * from test_table")),
        (BigQueryValueCheckOperator, dict(sql="Select * from test_table", pass_value=95)),
        (BigQueryIntervalCheckOperator, dict(table=TEST_TABLE_ID, metrics_thresholds={"COUNT(*)": 1.5})),
    ],
)
class TestBigQueryCheckOperators:
    @mock.patch("airflow.providers.google.cloud.operators.bigquery._BigQueryDbHookMixin.get_db_hook")
    def test_get_db_hook(
        self,
        mock_get_db_hook,
        operator_class,
        kwargs,
    ):
        operator = operator_class(task_id=TASK_ID, gcp_conn_id="google_cloud_default", **kwargs)
        operator.get_db_hook()
        mock_get_db_hook.assert_called_once()


class TestBigQueryUpsertTableOperator:
    @mock.patch("airflow.providers.google.cloud.operators.bigquery.BigQueryHook")
    def test_execute(self, mock_hook):
        operator = BigQueryUpsertTableOperator(
            task_id=TASK_ID,
            dataset_id=TEST_DATASET,
            table_resource=TEST_TABLE_RESOURCES,
            project_id=TEST_GCP_PROJECT_ID,
        )

        operator.execute(context=MagicMock())
        mock_hook.return_value.run_table_upsert.assert_called_once_with(
            dataset_id=TEST_DATASET, project_id=TEST_GCP_PROJECT_ID, table_resource=TEST_TABLE_RESOURCES
        )

    @mock.patch("airflow.providers.google.cloud.operators.bigquery.BigQueryHook")
    def test_get_openlineage_facets_on_complete(self, mock_hook):
        table_resource = {
            "tableReference": {
                "projectId": TEST_GCP_PROJECT_ID,
                "datasetId": TEST_DATASET,
                "tableId": TEST_TABLE_ID,
            },
            "description": "Table description.",
            "schema": {
                "fields": [
                    {"name": "field1", "type": "STRING", "description": "field1 description"},
                    {"name": "field2", "type": "INTEGER"},
                ]
            },
        }
        mock_hook.return_value.run_table_upsert.return_value = table_resource
        operator = BigQueryUpsertTableOperator(
            task_id=TASK_ID,
            dataset_id=TEST_DATASET,
            table_resource=TEST_TABLE_RESOURCES,
            project_id=TEST_GCP_PROJECT_ID,
        )
        operator.execute(context=MagicMock())

        result = operator.get_openlineage_facets_on_complete(None)
        assert not result.run_facets
        assert not result.job_facets
        assert not result.inputs
        assert len(result.outputs) == 1
        assert result.outputs[0].namespace == BIGQUERY_NAMESPACE
        assert result.outputs[0].name == f"{TEST_GCP_PROJECT_ID}.{TEST_DATASET}.{TEST_TABLE_ID}"
        assert result.outputs[0].facets == {
            "schema": SchemaDatasetFacet(
                fields=[
                    SchemaDatasetFacetFields(name="field1", type="STRING", description="field1 description"),
                    SchemaDatasetFacetFields(name="field2", type="INTEGER"),
                ]
            ),
            "documentation": DocumentationDatasetFacet(description="Table description."),
        }


class TestBigQueryInsertJobOperator:
    @mock.patch("airflow.providers.google.cloud.operators.bigquery.BigQueryHook")
    def test_execute_query_success(self, mock_hook):
        job_id = "123456"
        hash_ = "hash"
        real_job_id = f"{job_id}_{hash_}"

        configuration = {
            "query": {
                "query": "SELECT * FROM any",
                "useLegacySql": False,
            }
        }
        mock_hook.return_value.insert_job.return_value = MagicMock(
            state="DONE", job_id=real_job_id, error_result=False
        )
        mock_hook.return_value.generate_job_id.return_value = real_job_id

        op = BigQueryInsertJobOperator(
            task_id="insert_query_job",
            configuration=configuration,
            location=TEST_DATASET_LOCATION,
            job_id=job_id,
            project_id=TEST_GCP_PROJECT_ID,
        )
        result = op.execute(context=MagicMock())
        assert configuration["labels"] == {"airflow-dag": "adhoc_airflow", "airflow-task": "insert_query_job"}

        mock_hook.return_value.insert_job.assert_called_once_with(
            configuration=configuration,
            location=TEST_DATASET_LOCATION,
            job_id=real_job_id,
            nowait=True,
            project_id=TEST_GCP_PROJECT_ID,
            retry=DEFAULT_RETRY,
            timeout=None,
        )

        assert result == real_job_id

    @mock.patch("airflow.providers.google.cloud.operators.bigquery.BigQueryHook")
    def test_execute_copy_success(self, mock_hook):
        job_id = "123456"
        hash_ = "hash"
        real_job_id = f"{job_id}_{hash_}"

        configuration = {
            "copy": {
                "sourceTable": "aaa",
                "destinationTable": "bbb",
            }
        }
        mock_configuration = {
            "configuration": configuration,
            "jobReference": "a",
        }
        mock_hook.return_value.insert_job.return_value = MagicMock(
            state="DONE", job_id=real_job_id, error_result=False
        )
        mock_hook.return_value.generate_job_id.return_value = real_job_id
        mock_hook.return_value.insert_job.return_value.to_api_repr.return_value = mock_configuration

        op = BigQueryInsertJobOperator(
            task_id="copy_query_job",
            configuration=configuration,
            location=TEST_DATASET_LOCATION,
            job_id=job_id,
            project_id=TEST_GCP_PROJECT_ID,
        )
        result = op.execute(context=MagicMock())
        assert configuration["labels"] == {"airflow-dag": "adhoc_airflow", "airflow-task": "copy_query_job"}

        mock_hook.return_value.insert_job.assert_called_once_with(
            configuration=configuration,
            location=TEST_DATASET_LOCATION,
            job_id=real_job_id,
            nowait=True,
            project_id=TEST_GCP_PROJECT_ID,
            retry=DEFAULT_RETRY,
            timeout=None,
        )

        assert result == real_job_id

    @mock.patch("airflow.providers.google.cloud.operators.bigquery.BigQueryHook")
    def test_on_kill(self, mock_hook):
        job_id = "123456"
        hash_ = "hash"
        real_job_id = f"{job_id}_{hash_}"

        configuration = {
            "query": {
                "query": "SELECT * FROM any",
                "useLegacySql": False,
            }
        }
        mock_hook.return_value.insert_job.return_value = MagicMock(
            state="DONE", job_id=real_job_id, error_result=False
        )
        mock_hook.return_value.generate_job_id.return_value = real_job_id

        op = BigQueryInsertJobOperator(
            task_id="insert_query_job",
            configuration=configuration,
            location=TEST_DATASET_LOCATION,
            job_id=job_id,
            project_id=TEST_GCP_PROJECT_ID,
            cancel_on_kill=False,
        )
        op.execute(context=MagicMock())

        op.on_kill()
        mock_hook.return_value.cancel_job.assert_not_called()

        op.cancel_on_kill = True
        op.on_kill()
        mock_hook.return_value.cancel_job.assert_called_once_with(
            job_id=real_job_id,
            location=TEST_DATASET_LOCATION,
            project_id=TEST_GCP_PROJECT_ID,
        )

    @mock.patch("airflow.providers.google.cloud.operators.bigquery.BigQueryHook")
    @mock.patch("airflow.providers.google.cloud.hooks.bigquery.BigQueryJob")
    def test_on_kill_after_execution_timeout(self, mock_job, mock_hook):
        job_id = "123456"
        hash_ = "hash"
        real_job_id = f"{job_id}_{hash_}"

        configuration = {
            "query": {
                "query": "SELECT * FROM any",
                "useLegacySql": False,
            }
        }

        mock_job.job_id = real_job_id
        mock_job.error_result = False
        mock_job.state = "DONE"
        mock_job.result.side_effect = AirflowTaskTimeout()

        mock_hook.return_value.insert_job.return_value = mock_job
        mock_hook.return_value.generate_job_id.return_value = real_job_id

        op = BigQueryInsertJobOperator(
            task_id="insert_query_job",
            configuration=configuration,
            location=TEST_DATASET_LOCATION,
            job_id=job_id,
            project_id=TEST_GCP_PROJECT_ID,
            cancel_on_kill=True,
        )
        with pytest.raises(AirflowTaskTimeout):
            op.execute(context=MagicMock())

        op.on_kill()
        mock_hook.return_value.cancel_job.assert_called_once_with(
            job_id=real_job_id,
            location=TEST_DATASET_LOCATION,
            project_id=TEST_GCP_PROJECT_ID,
        )

    @mock.patch("airflow.providers.google.cloud.operators.bigquery.BigQueryHook")
    def test_execute_failure(self, mock_hook):
        job_id = "123456"
        hash_ = "hash"
        real_job_id = f"{job_id}_{hash_}"

        configuration = {
            "query": {
                "query": "SELECT * FROM any",
                "useLegacySql": False,
            }
        }
        mock_hook.return_value.insert_job.return_value = MagicMock(
            state="DONE", job_id=real_job_id, error_result=True
        )
        mock_hook.return_value.generate_job_id.return_value = real_job_id

        op = BigQueryInsertJobOperator(
            task_id="insert_query_job",
            configuration=configuration,
            location=TEST_DATASET_LOCATION,
            job_id=job_id,
            project_id=TEST_GCP_PROJECT_ID,
        )
        with pytest.raises(AirflowException):
            op.execute(context=MagicMock())

    @mock.patch(
        "airflow.providers.google.cloud.operators.bigquery.BigQueryInsertJobOperator._handle_job_error"
    )
    @mock.patch("airflow.providers.google.cloud.operators.bigquery.BigQueryHook")
    def test_execute_reattach(self, mock_hook, _handle_job_error):
        job_id = "123456"
        hash_ = "hash"
        real_job_id = f"{job_id}_{hash_}"

        configuration = {
            "query": {
                "query": "SELECT * FROM any",
                "useLegacySql": False,
            }
        }

        mock_hook.return_value.insert_job.side_effect = Conflict("any")
        job = MagicMock(
            job_id=real_job_id,
            error_result=False,
            state="RUNNING",
            done=lambda: False,
        )
        mock_hook.return_value.get_job.return_value = job
        mock_hook.return_value.generate_job_id.return_value = real_job_id

        op = BigQueryInsertJobOperator(
            task_id="insert_query_job",
            configuration=configuration,
            location=TEST_DATASET_LOCATION,
            job_id=job_id,
            project_id=TEST_GCP_PROJECT_ID,
            reattach_states={"PENDING", "RUNNING"},
        )
        result = op.execute(context=MagicMock())

        mock_hook.return_value.get_job.assert_called_once_with(
            location=TEST_DATASET_LOCATION,
            job_id=real_job_id,
            project_id=TEST_GCP_PROJECT_ID,
        )

        job.result.assert_called_once_with(
            retry=DEFAULT_RETRY,
            timeout=None,
        )

        assert result == real_job_id

    @mock.patch("airflow.providers.google.cloud.operators.bigquery.BigQueryHook")
    def test_execute_reattach_to_done_state(self, mock_hook):
        job_id = "123456"
        hash_ = "hash"
        real_job_id = f"{job_id}_{hash_}"

        configuration = {
            "query": {
                "query": "SELECT * FROM any",
                "useLegacySql": False,
            }
        }

        mock_hook.return_value.insert_job.side_effect = Conflict("any")
        job = MagicMock(
            job_id=real_job_id,
            error_result=False,
            state="DONE",
            done=lambda: False,
        )
        mock_hook.return_value.get_job.return_value = job
        mock_hook.return_value.generate_job_id.return_value = real_job_id

        op = BigQueryInsertJobOperator(
            task_id="insert_query_job",
            configuration=configuration,
            location=TEST_DATASET_LOCATION,
            job_id=job_id,
            project_id=TEST_GCP_PROJECT_ID,
            reattach_states={"PENDING"},
        )
        with pytest.raises(AirflowException):
            # Not possible to reattach to any state if job is already DONE
            op.execute(context=MagicMock())

    @mock.patch("airflow.providers.google.cloud.operators.bigquery.BigQueryHook")
    def test_execute_force_rerun(self, mock_hook):
        job_id = "123456"
        hash_ = "hash"
        real_job_id = f"{job_id}_{hash_}"

        configuration = {
            "query": {
                "query": "SELECT * FROM any",
                "useLegacySql": False,
            }
        }

        job = MagicMock(
            state="DONE",
            job_id=real_job_id,
            error_result=False,
        )
        mock_hook.return_value.insert_job.return_value = job
        mock_hook.return_value.generate_job_id.return_value = real_job_id

        op = BigQueryInsertJobOperator(
            task_id="insert_query_job",
            configuration=configuration,
            location=TEST_DATASET_LOCATION,
            job_id=job_id,
            project_id=TEST_GCP_PROJECT_ID,
            force_rerun=True,
        )
        result = op.execute(context=MagicMock())

        mock_hook.return_value.insert_job.assert_called_once_with(
            configuration=configuration,
            location=TEST_DATASET_LOCATION,
            job_id=real_job_id,
            nowait=True,
            project_id=TEST_GCP_PROJECT_ID,
            retry=DEFAULT_RETRY,
            timeout=None,
        )

        assert result == real_job_id

    @mock.patch("airflow.providers.google.cloud.operators.bigquery.BigQueryHook")
    def test_execute_no_force_rerun(self, mock_hook):
        job_id = "123456"
        hash_ = "hash"
        real_job_id = f"{job_id}_{hash_}"

        configuration = {
            "query": {
                "query": "SELECT * FROM any",
                "useLegacySql": False,
            }
        }

        mock_hook.return_value.insert_job.side_effect = Conflict("any")
        mock_hook.return_value.generate_job_id.return_value = real_job_id
        job = MagicMock(
            job_id=real_job_id,
            error_result=False,
            state="DONE",
            done=lambda: True,
        )
        mock_hook.return_value.get_job.return_value = job

        op = BigQueryInsertJobOperator(
            task_id="insert_query_job",
            configuration=configuration,
            location=TEST_DATASET_LOCATION,
            job_id=job_id,
            project_id=TEST_GCP_PROJECT_ID,
            reattach_states={"PENDING"},
        )
        # No force rerun
        with pytest.raises(AirflowException):
            op.execute(context=MagicMock())

    @mock.patch("airflow.providers.google.cloud.operators.bigquery.BigQueryInsertJobOperator.defer")
    @mock.patch("airflow.providers.google.cloud.operators.bigquery.BigQueryHook")
    def test_bigquery_insert_job_operator_async_finish_before_deferred(self, mock_hook, mock_defer, caplog):
        job_id = "123456"
        hash_ = "hash"
        real_job_id = f"{job_id}_{hash_}"

        configuration = {
            "query": {
                "query": "SELECT * FROM any",
                "useLegacySql": False,
            }
        }
        mock_hook.return_value.insert_job.return_value = MagicMock(
            state="DONE", job_id=real_job_id, error_result=False
        )
        mock_hook.return_value.insert_job.return_value.running.return_value = False

        op = BigQueryInsertJobOperator(
            task_id="insert_query_job",
            configuration=configuration,
            location=TEST_DATASET_LOCATION,
            job_id=job_id,
            project_id=TEST_GCP_PROJECT_ID,
            deferrable=True,
        )

        result = op.execute(context=MagicMock())

        assert not mock_defer.called
        assert "Current state of job" in caplog.text
        assert result == real_job_id

    @mock.patch("airflow.providers.google.cloud.operators.bigquery.BigQueryInsertJobOperator.defer")
    @mock.patch("airflow.providers.google.cloud.operators.bigquery.BigQueryHook")
    def test_bigquery_insert_job_operator_async_error_before_deferred(self, mock_hook, mock_defer, caplog):
        job_id = "123456"
        hash_ = "hash"
        real_job_id = f"{job_id}_{hash_}"

        configuration = {
            "query": {
                "query": "SELECT * FROM any",
                "useLegacySql": False,
            }
        }
        mock_hook.return_value.insert_job.return_value = MagicMock(
            state="DONE", job_id=real_job_id, error_result=True
        )
        mock_hook.return_value.insert_job.return_value.running.return_value = False

        op = BigQueryInsertJobOperator(
            task_id="insert_query_job",
            configuration=configuration,
            location=TEST_DATASET_LOCATION,
            job_id=job_id,
            project_id=TEST_GCP_PROJECT_ID,
            deferrable=True,
        )

        with pytest.raises(AirflowException) as exc:
            op.execute(MagicMock())

        assert str(exc.value) == f"BigQuery job {real_job_id} failed: True"

    @pytest.mark.db_test
    @mock.patch("airflow.providers.google.cloud.operators.bigquery.BigQueryHook")
    def test_bigquery_insert_job_operator_async(self, mock_hook, create_task_instance_of_operator):
        """
        Asserts that a task is deferred and a BigQueryInsertJobTrigger will be fired
        when the BigQueryInsertJobOperator is executed with deferrable=True.
        """
        job_id = "123456"
        hash_ = "hash"
        real_job_id = f"{job_id}_{hash_}"

        configuration = {
            "query": {
                "query": "SELECT * FROM any",
                "useLegacySql": False,
            }
        }
        mock_hook.return_value.insert_job.return_value = MagicMock(job_id=real_job_id, error_result=False)

        ti = create_task_instance_of_operator(
            BigQueryInsertJobOperator,
            dag_id="dag_id",
            task_id="insert_query_job",
            configuration=configuration,
            location=TEST_DATASET_LOCATION,
            job_id=job_id,
            project_id=TEST_GCP_PROJECT_ID,
            deferrable=True,
        )

        with pytest.raises(TaskDeferred) as exc:
            ti.task.execute(MagicMock())

        assert isinstance(exc.value.trigger, BigQueryInsertJobTrigger), (
            "Trigger is not a BigQueryInsertJobTrigger"
        )

    @pytest.mark.db_test
    @mock.patch("airflow.providers.google.cloud.operators.bigquery.BigQueryHook")
    def test_bigquery_insert_job_operator_async_inherits_hook_project_id_when_non_given(
        self, mock_hook, create_task_instance_of_operator
    ):
        """
        Asserts that a deferred task of type BigQueryInsertJobTrigger will assume the project_id
        of the hook that is used within the BigQueryInsertJobOperator when there is no
        project_id passed to the BigQueryInsertJobOperator.
        """
        job_id = "123456"

        configuration = {
            "query": {
                "query": "SELECT * FROM any",
                "useLegacySql": False,
            }
        }
        mock_hook.return_value.project_id = TEST_GCP_PROJECT_ID

        ti = create_task_instance_of_operator(
            BigQueryInsertJobOperator,
            dag_id="dag_id",
            task_id="insert_query_job",
            configuration=configuration,
            location=TEST_DATASET_LOCATION,
            job_id=job_id,
            deferrable=True,
            project_id=None,
        )

        with pytest.raises(TaskDeferred) as exc:
            ti.task.execute(MagicMock())

        assert isinstance(exc.value.trigger, BigQueryInsertJobTrigger), (
            "Trigger is not a BigQueryInsertJobTrigger"
        )

        assert exc.value.trigger.project_id == TEST_GCP_PROJECT_ID

    def test_bigquery_insert_job_operator_execute_failure(self):
        """Tests that an AirflowException is raised in case of error event"""
        configuration = {
            "query": {
                "query": "SELECT * FROM any",
                "useLegacySql": False,
            }
        }
        job_id = "123456"

        operator = BigQueryInsertJobOperator(
            task_id="insert_query_job",
            configuration=configuration,
            location=TEST_DATASET_LOCATION,
            job_id=job_id,
            project_id=TEST_GCP_PROJECT_ID,
            deferrable=True,
        )

        with pytest.raises(AirflowException):
            operator.execute_complete(
                context=None, event={"status": "error", "message": "test failure message"}
            )

    @pytest.mark.db_test
    def test_bigquery_insert_job_operator_execute_complete(self, create_task_instance_of_operator):
        """Asserts that logging occurs as expected"""
        configuration = {
            "query": {
                "query": "SELECT * FROM any",
                "useLegacySql": False,
            }
        }
        job_id = "123456"

        ti = create_task_instance_of_operator(
            BigQueryInsertJobOperator,
            dag_id="dag_id",
            task_id="insert_query_job",
            configuration=configuration,
            location=TEST_DATASET_LOCATION,
            job_id=job_id,
            project_id=TEST_GCP_PROJECT_ID,
            deferrable=True,
        )
        operator = ti.task
        with mock.patch.object(operator.log, "info") as mock_log_info:
            operator.execute_complete(
                context=MagicMock(),
                event={"status": "success", "message": "Job completed", "job_id": job_id},
            )
        mock_log_info.assert_called_with(
            "%s completed with response %s ", "insert_query_job", "Job completed"
        )

    def test_bigquery_insert_job_operator_execute_complete_reassigns_job_id(self):
        """Assert that we use job_id from event after deferral."""
        configuration = {
            "query": {
                "query": "SELECT * FROM any",
                "useLegacySql": False,
            }
        }
        job_id = "123456"

        operator = BigQueryInsertJobOperator(
            task_id="insert_query_job",
            configuration=configuration,
            location=TEST_DATASET_LOCATION,
            job_id=None,  # We are not passing anything here on purpose
            project_id=TEST_GCP_PROJECT_ID,
            deferrable=True,
        )

        returned_job_id = operator.execute_complete(
            context=MagicMock(),
            event={"status": "success", "message": "Job completed", "job_id": job_id},
        )
        assert returned_job_id == job_id
        assert operator.job_id == job_id

    @pytest.mark.db_test
    @mock.patch(
        "airflow.providers.google.cloud.operators.bigquery.BigQueryInsertJobOperator._handle_job_error"
    )
    @mock.patch("airflow.providers.google.cloud.operators.bigquery.BigQueryHook")
    def test_bigquery_insert_job_operator_with_job_id_generate(
        self, mock_hook, _handle_job_error, create_task_instance_of_operator
    ):
        job_id = "123456"
        hash_ = "hash"
        real_job_id = f"{job_id}_{hash_}"

        configuration = {
            "query": {
                "query": "SELECT * FROM any",
                "useLegacySql": False,
            }
        }

        mock_hook.return_value.insert_job.side_effect = Conflict("any")
        job = MagicMock(
            job_id=real_job_id,
            error_result=False,
            state="PENDING",
            done=lambda: False,
        )
        mock_hook.return_value.get_job.return_value = job

        ti = create_task_instance_of_operator(
            BigQueryInsertJobOperator,
            dag_id="adhoc_airflow",
            task_id="insert_query_job",
            configuration=configuration,
            location=TEST_DATASET_LOCATION,
            job_id=job_id,
            project_id=TEST_GCP_PROJECT_ID,
            reattach_states={"PENDING"},
            deferrable=True,
        )

        with pytest.raises(TaskDeferred):
            ti.task.execute(MagicMock())

        mock_hook.return_value.generate_job_id.assert_called_once_with(
            job_id=job_id,
            dag_id="adhoc_airflow",
            task_id="insert_query_job",
            logical_date=ANY,
            configuration=configuration,
            force_rerun=True,
        )

    @mock.patch("airflow.providers.google.cloud.operators.bigquery.BigQueryHook")
    def test_execute_openlineage_events(self, mock_hook):
        job_id = "123456"
        hash_ = "hash"
        real_job_id = f"{job_id}_{hash_}"

        configuration = {
            "query": {
                "query": "SELECT * FROM test_table",
                "useLegacySql": False,
            }
        }
        mock_hook.return_value.insert_job.return_value = MagicMock(
            state="DONE", job_id=real_job_id, error_result=False
        )
        mock_hook.return_value.generate_job_id.return_value = real_job_id

        op = BigQueryInsertJobOperator(
            task_id="insert_query_job",
            configuration=configuration,
            location=TEST_DATASET_LOCATION,
            job_id=job_id,
            project_id=TEST_GCP_PROJECT_ID,
        )
        result = op.execute(context=MagicMock())

        mock_hook.return_value.insert_job.assert_called_once_with(
            configuration=configuration,
            location=TEST_DATASET_LOCATION,
            job_id=real_job_id,
            nowait=True,
            project_id=TEST_GCP_PROJECT_ID,
            retry=DEFAULT_RETRY,
            timeout=None,
        )

        assert result == real_job_id

        with open(os.path.dirname(__file__) + "/../utils/query_job_details.json") as f:
            job_details = json.loads(f.read())
        mock_hook.return_value.get_client.return_value.get_job.return_value._properties = job_details
        mock_hook.return_value.get_client.return_value.get_table.side_effect = Exception()

        lineage = op.get_openlineage_facets_on_complete(None)
        assert lineage.inputs == [
            InputDataset(namespace="bigquery", name="airflow-openlineage.new_dataset.test_table")
        ]

        assert lineage.run_facets == {
            "bigQueryJob": mock.ANY,
            "externalQuery": ExternalQueryRunFacet(externalQueryId=mock.ANY, source="bigquery"),
        }
        assert lineage.job_facets == {"sql": SQLJobFacet(query="SELECT * FROM test_table")}

    @mock.patch("airflow.providers.google.cloud.operators.bigquery.BigQueryHook")
    def test_execute_fails_openlineage_events(self, mock_hook):
        job_id = "1234"

        configuration = {
            "query": {
                "query": "SELECT * FROM test_table",
                "useLegacySql": False,
            }
        }
        operator = BigQueryInsertJobOperator(
            task_id="insert_query_job_failed",
            configuration=configuration,
            location=TEST_DATASET_LOCATION,
            job_id=job_id,
            project_id=TEST_GCP_PROJECT_ID,
        )
        mock_hook.return_value.generate_job_id.return_value = "1234"
        mock_hook.return_value.get_client.return_value.get_job.side_effect = RuntimeError()
        mock_hook.return_value.insert_job.side_effect = RuntimeError()

        with suppress(RuntimeError):
            operator.execute(MagicMock())
        lineage = operator.get_openlineage_facets_on_complete(None)

        assert isinstance(lineage.run_facets["errorMessage"], ErrorMessageRunFacet)

    @pytest.mark.db_test
    @mock.patch("airflow.providers.google.cloud.operators.bigquery.BigQueryHook")
    def test_execute_force_rerun_async(self, mock_hook, create_task_instance_of_operator):
        job_id = "123456"
        hash_ = "hash"
        real_job_id = f"{job_id}_{hash_}"
        mock_hook.return_value.generate_job_id.return_value = f"{job_id}_{hash_}"

        configuration = {
            "query": {
                "query": "SELECT * FROM any",
                "useLegacySql": False,
            }
        }

        mock_hook.return_value.insert_job.side_effect = Conflict("any")
        job = MagicMock(
            job_id=real_job_id,
            error_result=False,
            state="DONE",
            done=lambda: False,
        )
        mock_hook.return_value.get_job.return_value = job

        ti = create_task_instance_of_operator(
            BigQueryInsertJobOperator,
            dag_id="dag_id",
            task_id="insert_query_job",
            configuration=configuration,
            location=TEST_DATASET_LOCATION,
            job_id=job_id,
            project_id=TEST_GCP_PROJECT_ID,
            reattach_states={"PENDING"},
            deferrable=True,
        )

        with pytest.raises(AirflowException) as exc:
            ti.task.execute(MagicMock())

        expected_exception_msg = (
            f"Job with id: {real_job_id} already exists and is in {job.state} state. "
            f"If you want to force rerun it consider setting `force_rerun=True`."
            f"Or, if you want to reattach in this scenario add {job.state} to `reattach_states`"
        )

        assert str(exc.value) == expected_exception_msg

        mock_hook.return_value.get_job.assert_called_once_with(
            location=TEST_DATASET_LOCATION,
            job_id=real_job_id,
            project_id=TEST_GCP_PROJECT_ID,
        )

    @mock.patch("airflow.providers.google.cloud.operators.bigquery.BigQueryHook")
    def test_execute_adds_to_existing_labels(self, mock_hook):
        job_id = "123456"
        hash_ = "hash"
        real_job_id = f"{job_id}_{hash_}"

        configuration = {
            "query": {
                "query": "SELECT * FROM any",
                "useLegacySql": False,
            },
            "labels": {"foo": "bar"},
        }
        mock_hook.return_value.insert_job.return_value = MagicMock(
            state="DONE", job_id=real_job_id, error_result=False
        )
        mock_hook.return_value.generate_job_id.return_value = real_job_id

        op = BigQueryInsertJobOperator(
            task_id="insert_query_job",
            configuration=configuration,
            location=TEST_DATASET_LOCATION,
            job_id=job_id,
            project_id=TEST_GCP_PROJECT_ID,
        )
        op.execute(context=MagicMock())
        assert configuration["labels"] == {
            "foo": "bar",
            "airflow-dag": "adhoc_airflow",
            "airflow-task": "insert_query_job",
        }

    @mock.patch("airflow.providers.google.cloud.operators.bigquery.BigQueryHook")
    def test_execute_respects_explicit_no_labels(self, mock_hook):
        job_id = "123456"
        hash_ = "hash"
        real_job_id = f"{job_id}_{hash_}"

        configuration = {
            "query": {
                "query": "SELECT * FROM any",
                "useLegacySql": False,
            },
            "labels": None,
        }
        mock_hook.return_value.insert_job.return_value = MagicMock(
            state="DONE", job_id=real_job_id, error_result=False
        )
        mock_hook.return_value.generate_job_id.return_value = real_job_id

        op = BigQueryInsertJobOperator(
            task_id="insert_query_job",
            configuration=configuration,
            location=TEST_DATASET_LOCATION,
            job_id=job_id,
            project_id=TEST_GCP_PROJECT_ID,
        )
        op.execute(context=MagicMock())
        assert configuration["labels"] is None

    def test_task_label_too_big(self):
        configuration = {
            "query": {
                "query": "SELECT * FROM any",
                "useLegacySql": False,
            },
        }
        op = BigQueryInsertJobOperator(
            task_id="insert_query_job_except_this_task_id_is_really_really_really_really_long",
            configuration=configuration,
            location=TEST_DATASET_LOCATION,
            project_id=TEST_GCP_PROJECT_ID,
        )
        op._add_job_labels()
        assert "labels" not in configuration

    @pytest.mark.db_test
    def test_dag_label_too_big(self, dag_maker):
        configuration = {
            "query": {
                "query": "SELECT * FROM any",
                "useLegacySql": False,
            },
        }
        with dag_maker("adhoc_airflow_except_this_task_id_is_really_really_really_really_long"):
            op = BigQueryInsertJobOperator(
                task_id="insert_query_job",
                configuration=configuration,
                location=TEST_DATASET_LOCATION,
                project_id=TEST_GCP_PROJECT_ID,
            )
        op._add_job_labels()
        assert "labels" not in configuration

    @pytest.mark.db_test
    def test_labels_lowercase(self, dag_maker):
        configuration = {
            "query": {
                "query": "SELECT * FROM any",
                "useLegacySql": False,
            },
        }
        with dag_maker("YELLING_DAG_NAME"):
            op = BigQueryInsertJobOperator(
                task_id="YELLING_TASK_ID",
                configuration=configuration,
                location=TEST_DATASET_LOCATION,
                project_id=TEST_GCP_PROJECT_ID,
            )
        op._add_job_labels()
        assert configuration["labels"]["airflow-dag"] == "yelling_dag_name"
        assert configuration["labels"]["airflow-task"] == "yelling_task_id"

    @pytest.mark.db_test
    def test_labels_starting_with_numbers(self, dag_maker):
        configuration = {
            "query": {
                "query": "SELECT * FROM any",
                "useLegacySql": False,
            },
        }
        with dag_maker("123_dag"):
            op = BigQueryInsertJobOperator(
                task_id="123_task",
                configuration=configuration,
                location=TEST_DATASET_LOCATION,
                project_id=TEST_GCP_PROJECT_ID,
            )
        op._add_job_labels()
        assert configuration["labels"]["airflow-dag"] == "123_dag"
        assert configuration["labels"]["airflow-task"] == "123_task"

    @pytest.mark.db_test
    def test_labels_starting_with_underscore(self, dag_maker):
        configuration = {
            "query": {
                "query": "SELECT * FROM any",
                "useLegacySql": False,
            },
        }
        with dag_maker("_dag_starting_with_underscore"):
            op = BigQueryInsertJobOperator(
                task_id="_task_starting_with_underscore",
                configuration=configuration,
                location=TEST_DATASET_LOCATION,
                project_id=TEST_GCP_PROJECT_ID,
            )
        op._add_job_labels()
        assert "labels" in configuration
        assert configuration["labels"]["airflow-dag"] == "_dag_starting_with_underscore"
        assert configuration["labels"]["airflow-task"] == "_task_starting_with_underscore"

    @pytest.mark.db_test
    def test_labels_starting_with_hyphen(self, dag_maker):
        configuration = {
            "query": {
                "query": "SELECT * FROM any",
                "useLegacySql": False,
            },
        }
        with dag_maker("-dag-starting-with-hyphen"):
            op = BigQueryInsertJobOperator(
                task_id="-task-starting-with-hyphen",
                configuration=configuration,
                location=TEST_DATASET_LOCATION,
                project_id=TEST_GCP_PROJECT_ID,
            )
        op._add_job_labels()
        assert "labels" in configuration
        assert configuration["labels"]["airflow-dag"] == "-dag-starting-with-hyphen"
        assert configuration["labels"]["airflow-task"] == "-task-starting-with-hyphen"

    def test_labels_invalid_names(self, dag_maker):
        configuration = {
            "query": {
                "query": "SELECT * FROM any",
                "useLegacySql": False,
            },
        }
        op = BigQueryInsertJobOperator(
            task_id="task_id_with_exactly_64_characters_00000000000000000000000000000",
            configuration=configuration,
            location=TEST_DATASET_LOCATION,
            project_id=TEST_GCP_PROJECT_ID,
        )
        op._add_job_labels()
        assert "labels" not in configuration

    @pytest.mark.db_test
    def test_labels_replace_dots_with_hyphens(self, dag_maker):
        configuration = {
            "query": {
                "query": "SELECT * FROM any",
                "useLegacySql": False,
            },
        }
        with dag_maker("dag_replace_dots_with_hyphens"):
            op = BigQueryInsertJobOperator(
                task_id="task.name.with.dots",
                configuration=configuration,
                location=TEST_DATASET_LOCATION,
                project_id=TEST_GCP_PROJECT_ID,
            )
        op._add_job_labels()
        assert "labels" in configuration
        assert configuration["labels"]["airflow-dag"] == "dag_replace_dots_with_hyphens"
        assert configuration["labels"]["airflow-task"] == "task-name-with-dots"

        with dag_maker("dag_with_taskgroup"):
            with TaskGroup("task_group"):
                op = BigQueryInsertJobOperator(
                    task_id="task_name",
                    configuration=configuration,
                    location=TEST_DATASET_LOCATION,
                    project_id=TEST_GCP_PROJECT_ID,
                )
        op._add_job_labels()
        assert "labels" in configuration
        assert configuration["labels"]["airflow-dag"] == "dag_with_taskgroup"
        assert configuration["labels"]["airflow-task"] == "task_group-task_name"

    @pytest.mark.db_test
    def test_labels_with_task_group_prefix_group_id(self, dag_maker):
        configuration = {
            "query": {
                "query": "SELECT * FROM any",
                "useLegacySql": False,
            },
        }
        with dag_maker("dag_with_taskgroup"):
            with TaskGroup("task_group", prefix_group_id=False):
                op = BigQueryInsertJobOperator(
                    task_id="task_name",
                    configuration=configuration,
                    location=TEST_DATASET_LOCATION,
                    project_id=TEST_GCP_PROJECT_ID,
                )
        op._add_job_labels()
        assert "labels" in configuration
        assert configuration["labels"]["airflow-dag"] == "dag_with_taskgroup"
        assert configuration["labels"]["airflow-task"] == "task_name"

        with dag_maker("dag_with_taskgroup_prefix_group_id_false_with_dots"):
            with TaskGroup("task_group_prefix_group_id_false", prefix_group_id=False):
                op = BigQueryInsertJobOperator(
                    task_id="task.name.with.dots",
                    configuration=configuration,
                    location=TEST_DATASET_LOCATION,
                    project_id=TEST_GCP_PROJECT_ID,
                )
        op._add_job_labels()
        assert "labels" in configuration
        assert configuration["labels"]["airflow-dag"] == "dag_with_taskgroup_prefix_group_id_false_with_dots"
        assert configuration["labels"]["airflow-task"] == "task-name-with-dots"

    def test_handle_job_error_raises_on_error_result_or_error(self, caplog):
        caplog.set_level(logging.ERROR)
        configuration = {
            "query": {
                "query": "SELECT * FROM any",
                "useLegacySql": False,
            },
        }
        op = BigQueryInsertJobOperator(
            task_id="task.with.dots.is.allowed",
            configuration=configuration,
            location=TEST_DATASET_LOCATION,
            project_id=TEST_GCP_PROJECT_ID,
            job_id="12345",
        )
        # Test error_result
        job_with_error_result = create_bigquery_job(error_result="Job failed due to some issue")
        with pytest.raises(
            AirflowException, match="BigQuery job mock-job-id failed: Job failed due to some issue"
        ):
            op._handle_job_error(job_with_error_result)

        # Test errors
        job_with_error = create_bigquery_job(errors=["Some transient error"])
        op._handle_job_error(job_with_error)

        assert "Some transient error" in caplog.text

        # Test empty error object
        job_empty_error = create_bigquery_job(state="RUNNING")
        with pytest.raises(AirflowException, match="Job failed with state: RUNNING"):
            op._handle_job_error(job_empty_error)


class TestBigQueryIntervalCheckOperator:
    def test_bigquery_interval_check_operator_execute_complete(self):
        """Asserts that logging occurs as expected"""

        operator = BigQueryIntervalCheckOperator(
            task_id="bq_interval_check_operator_execute_complete",
            table="test_table",
            metrics_thresholds={"COUNT(*)": 1.5},
            location=TEST_DATASET_LOCATION,
            deferrable=True,
        )

        with mock.patch.object(operator.log, "info") as mock_log_info:
            operator.execute_complete(context=None, event={"status": "success", "message": "Job completed"})
        mock_log_info.assert_called_with(
            "%s completed with response %s ", "bq_interval_check_operator_execute_complete", "Job completed"
        )

    def test_bigquery_interval_check_operator_execute_failure(self):
        """Tests that an AirflowException is raised in case of error event"""

        operator = BigQueryIntervalCheckOperator(
            task_id="bq_interval_check_operator_execute_complete",
            table="test_table",
            metrics_thresholds={"COUNT(*)": 1.5},
            location=TEST_DATASET_LOCATION,
            deferrable=True,
        )

        with pytest.raises(AirflowException):
            operator.execute_complete(
                context=None, event={"status": "error", "message": "test failure message"}
            )

    def test_bigquery_interval_check_operator_project_id(self):
        operator = BigQueryIntervalCheckOperator(
            task_id="bq_interval_check_operator_project_id",
            table="test_table",
            metrics_thresholds={"COUNT(*)": 1.5},
            location=TEST_DATASET_LOCATION,
            project_id=TEST_JOB_PROJECT_ID,
        )

        assert operator.project_id == TEST_JOB_PROJECT_ID

    @pytest.mark.db_test
    @mock.patch("airflow.providers.google.cloud.operators.bigquery.BigQueryHook")
    def test_bigquery_interval_check_operator_async(self, mock_hook, create_task_instance_of_operator):
        """
        Asserts that a task is deferred and a BigQueryIntervalCheckTrigger will be fired
        when the BigQueryIntervalCheckOperator is executed with deferrable=True.
        """
        job_id = "123456"
        hash_ = "hash"
        real_job_id = f"{job_id}_{hash_}"

        mock_hook.return_value.insert_job.return_value = MagicMock(job_id=real_job_id, error_result=False)

        ti = create_task_instance_of_operator(
            BigQueryIntervalCheckOperator,
            dag_id="dag_id",
            task_id="bq_interval_check_operator_execute_complete",
            table="test_table",
            metrics_thresholds={"COUNT(*)": 1.5},
            location=TEST_DATASET_LOCATION,
            deferrable=True,
        )

        with pytest.raises(TaskDeferred) as exc:
            ti.task.execute(MagicMock())

        assert isinstance(exc.value.trigger, BigQueryIntervalCheckTrigger), (
            "Trigger is not a BigQueryIntervalCheckTrigger"
        )

    @pytest.mark.db_test
    @mock.patch("airflow.providers.google.cloud.operators.bigquery.BigQueryHook")
    def test_bigquery_interval_check_operator_with_project_id(
        self, mock_hook, create_task_instance_of_operator
    ):
        """
        Test BigQueryIntervalCheckOperator with a specified project_id.
        Ensure that the bq_project_id is passed correctly when submitting the job.
        """
        job_id = "123456"
        hash_ = "hash"
        real_job_id = f"{job_id}_{hash_}"

        project_id = "test-project-id"
        ti = create_task_instance_of_operator(
            BigQueryIntervalCheckOperator,
            dag_id="dag_id",
            task_id="bq_interval_check_operator_with_project_id",
            table="test_table",
            metrics_thresholds={"COUNT(*)": 1.5},
            location=TEST_DATASET_LOCATION,
            deferrable=True,
            project_id=project_id,
        )

        mock_hook.return_value.insert_job.return_value = MagicMock(job_id=real_job_id, error_result=False)

        with pytest.raises(TaskDeferred):
            ti.task.execute(MagicMock())

        mock_hook.return_value.insert_job.assert_called_with(
            configuration=mock.ANY,
            project_id=project_id,
            location=TEST_DATASET_LOCATION,
            job_id=mock.ANY,
            nowait=True,
        )

    @pytest.mark.db_test
    @mock.patch("airflow.providers.google.cloud.operators.bigquery.BigQueryHook")
    def test_bigquery_interval_check_operator_without_project_id(
        self, mock_hook, create_task_instance_of_operator
    ):
        """
        Test BigQueryIntervalCheckOperator without a specified project_id.
        Ensure that the project_id falls back to the hook.project_id as previously implemented.
        """
        job_id = "123456"
        hash_ = "hash"
        real_job_id = f"{job_id}_{hash_}"

        project_id = "test-project-id"
        ti = create_task_instance_of_operator(
            BigQueryIntervalCheckOperator,
            dag_id="dag_id",
            task_id="bq_interval_check_operator_without_project_id",
            table="test_table",
            metrics_thresholds={"COUNT(*)": 1.5},
            location=TEST_DATASET_LOCATION,
            deferrable=True,
        )

        mock_hook.return_value.project_id = project_id
        mock_hook.return_value.insert_job.return_value = MagicMock(job_id=real_job_id, error_result=False)

        with pytest.raises(TaskDeferred):
            ti.task.execute(MagicMock())

        mock_hook.return_value.insert_job.assert_called_with(
            configuration=mock.ANY,
            project_id=mock_hook.return_value.project_id,
            location=TEST_DATASET_LOCATION,
            job_id=mock.ANY,
            nowait=True,
        )

    @mock.patch("airflow.providers.google.cloud.operators.bigquery.BigQueryHook")
    @mock.patch("airflow.providers.google.cloud.hooks.bigquery.BigQueryJob")
    def test_encryption_configuration_deferrable_mode(self, mock_job, mock_hook):
        encryption_configuration = {
            "kmsKeyName": "projects/PROJECT/locations/LOCATION/keyRings/KEY_RING/cryptoKeys/KEY",
        }

        mock_hook.return_value.insert_job.return_value = mock_job
        mock_hook.return_value.project_id = TEST_GCP_PROJECT_ID

        operator = BigQueryIntervalCheckOperator(
            task_id="TASK_ID",
            encryption_configuration=encryption_configuration,
            location=TEST_DATASET_LOCATION,
            metrics_thresholds={"COUNT(*)": 1.5},
            table=TEST_TABLE_ID,
            deferrable=True,
        )
        with pytest.raises(TaskDeferred):
            operator.execute(MagicMock())
        mock_hook.return_value.insert_job.assert_called_with(
            configuration={
                "query": {
                    "query": """SELECT COUNT(*) FROM test-table-id WHERE ds='{{ macros.ds_add(ds, -7) }}'""",
                    "useLegacySql": True,
                    "destinationEncryptionConfiguration": encryption_configuration,
                }
            },
            project_id=TEST_GCP_PROJECT_ID,
            location=TEST_DATASET_LOCATION,
            job_id="",
            nowait=True,
        )


class TestBigQueryCheckOperator:
    @pytest.mark.db_test
    @mock.patch("airflow.providers.google.cloud.operators.bigquery.BigQueryCheckOperator._validate_records")
    @mock.patch("airflow.providers.google.cloud.operators.bigquery.BigQueryCheckOperator.defer")
    @mock.patch("airflow.providers.google.cloud.operators.bigquery.BigQueryHook")
    def test_bigquery_check_operator_async_finish_before_deferred(
        self, mock_hook, mock_defer, mock_validate_records, create_task_instance_of_operator
    ):
        job_id = "123456"
        hash_ = "hash"
        real_job_id = f"{job_id}_{hash_}"

        mocked_job = MagicMock(job_id=real_job_id, error_result=False)
        mocked_job.result.return_value = iter([(1, 2, 3)])  # mock rows generator
        mock_hook.return_value.insert_job.return_value = mocked_job
        mock_hook.return_value.insert_job.return_value.running.return_value = False

        ti = create_task_instance_of_operator(
            BigQueryCheckOperator,
            dag_id="dag_id",
            task_id="bq_check_operator_job",
            sql="SELECT * FROM any",
            location=TEST_DATASET_LOCATION,
            deferrable=True,
        )

        ti.task.execute(MagicMock())
        mock_defer.assert_not_called()
        mock_validate_records.assert_called_once_with((1, 2, 3))

    @pytest.mark.db_test
    @mock.patch("airflow.providers.google.cloud.operators.bigquery.BigQueryCheckOperator._validate_records")
    @mock.patch("airflow.providers.google.cloud.operators.bigquery.BigQueryHook")
    def test_bigquery_check_operator_query_parameters_passing(
        self, mock_hook, mock_validate_records, create_task_instance_of_operator
    ):
        job_id = "123456"
        hash_ = "hash"
        real_job_id = f"{job_id}_{hash_}"
        query_params = [ScalarQueryParameter("test_param", "INT64", 1)]

        mocked_job = MagicMock(job_id=real_job_id, error_result=False)
        mocked_job.result.return_value = iter([(1, 2, 3)])  # mock rows generator
        mock_hook.return_value.insert_job.return_value = mocked_job
        mock_hook.return_value.insert_job.return_value.running.return_value = False

        ti = create_task_instance_of_operator(
            BigQueryCheckOperator,
            dag_id="dag_id",
            task_id="bq_check_operator_query_params_job",
            sql="SELECT * FROM any WHERE test_param = @test_param",
            location=TEST_DATASET_LOCATION,
            deferrable=True,
            query_params=query_params,
        )

        ti.task.execute(MagicMock())
        mock_validate_records.assert_called_once_with((1, 2, 3))

    @pytest.mark.db_test
    @mock.patch("airflow.providers.google.cloud.operators.bigquery.BigQueryHook")
    def test_bigquery_check_operator_async_finish_with_error_before_deferred(
        self, mock_hook, create_task_instance_of_operator
    ):
        job_id = "123456"
        hash_ = "hash"
        real_job_id = f"{job_id}_{hash_}"

        mock_hook.return_value.insert_job.return_value = MagicMock(job_id=real_job_id, error_result=True)
        mock_hook.return_value.insert_job.return_value.running.return_value = False

        ti = create_task_instance_of_operator(
            BigQueryCheckOperator,
            dag_id="dag_id",
            task_id="bq_check_operator_job",
            sql="SELECT * FROM any",
            location=TEST_DATASET_LOCATION,
            deferrable=True,
        )

        with pytest.raises(AirflowException) as exc:
            ti.task.execute(MagicMock())

        assert str(exc.value) == f"BigQuery job {real_job_id} failed: True"

    @pytest.mark.db_test
    @mock.patch("airflow.providers.google.cloud.operators.bigquery.BigQueryHook")
    def test_bigquery_check_operator_async(self, mock_hook, create_task_instance_of_operator):
        """
        Asserts that a task is deferred and a BigQueryCheckTrigger will be fired
        when the BigQueryCheckOperator is executed with deferrable=True.
        """
        job_id = "123456"
        hash_ = "hash"
        real_job_id = f"{job_id}_{hash_}"

        mock_hook.return_value.insert_job.return_value = MagicMock(job_id=real_job_id, error_result=False)

        ti = create_task_instance_of_operator(
            BigQueryCheckOperator,
            dag_id="dag_id",
            task_id="bq_check_operator_job",
            sql="SELECT * FROM any",
            location=TEST_DATASET_LOCATION,
            deferrable=True,
        )

        with pytest.raises(TaskDeferred) as exc:
            ti.task.execute(MagicMock())

        assert isinstance(exc.value.trigger, BigQueryCheckTrigger), "Trigger is not a BigQueryCheckTrigger"

    def test_bigquery_check_operator_execute_failure(self):
        """Tests that an AirflowException is raised in case of error event"""

        operator = BigQueryCheckOperator(
            task_id="bq_check_operator_execute_failure",
            sql="SELECT * FROM any",
            location=TEST_DATASET_LOCATION,
            deferrable=True,
        )

        with pytest.raises(AirflowException):
            operator.execute_complete(
                context=None, event={"status": "error", "message": "test failure message"}
            )

    def test_bigquery_check_operator_project_id(self):
        operator = BigQueryCheckOperator(
            task_id="bq_check_operator_project_id",
            sql="SELECT * FROM any",
            location=TEST_DATASET_LOCATION,
            project_id=TEST_JOB_PROJECT_ID,
        )

        assert operator.project_id == TEST_JOB_PROJECT_ID

    def test_bigquery_check_op_execute_complete_with_no_records(self):
        """Asserts that exception is raised with correct expected exception message"""

        operator = BigQueryCheckOperator(
            task_id="bq_check_operator_execute_complete",
            sql="SELECT * FROM any",
            location=TEST_DATASET_LOCATION,
            deferrable=True,
        )

        with pytest.raises(AirflowException, match="The following query returned zero rows:"):
            operator.execute_complete(context=None, event={"status": "success", "records": None})

    def test_bigquery_check_op_execute_complete_with_non_boolean_records(self):
        """Executing a sql which returns a non-boolean value should raise exception"""

        test_sql = "SELECT * FROM any"

        operator = BigQueryCheckOperator(
            task_id="bq_check_operator_execute_complete",
            sql=test_sql,
            location=TEST_DATASET_LOCATION,
            deferrable=True,
        )

        expected_exception_msg = f"Test failed.\nQuery:\n{test_sql}\nResults:\n{[20, False]!s}"

        with pytest.raises(AirflowException) as exc:
            operator.execute_complete(context=None, event={"status": "success", "records": [20, False]})

        assert str(exc.value) == expected_exception_msg

    def test_bigquery_check_operator_execute_complete(self):
        """Asserts that logging occurs as expected"""

        operator = BigQueryCheckOperator(
            task_id="bq_check_operator_execute_complete",
            sql="SELECT * FROM any",
            location=TEST_DATASET_LOCATION,
            deferrable=True,
        )

        with mock.patch.object(operator.log, "info") as mock_log_info:
            operator.execute_complete(context=None, event={"status": "success", "records": [20]})
        mock_log_info.assert_called_with("Success.")


class TestBigQueryValueCheckOperator:
    @pytest.mark.db_test
    @mock.patch("airflow.providers.google.cloud.operators.bigquery.BigQueryHook")
    def test_bigquery_value_check_async(self, mock_hook, create_task_instance_of_operator):
        """
        Asserts that a task is deferred and a BigQueryValueCheckTrigger will be fired
        when the BigQueryValueCheckOperator with deferrable=True is executed.
        """
        ti = create_task_instance_of_operator(
            BigQueryValueCheckOperator,
            dag_id="dag_id",
            task_id="check_value",
            sql="SELECT COUNT(*) FROM Any",
            pass_value=2,
            use_legacy_sql=True,
            deferrable=True,
        )
        job_id = "123456"
        hash_ = "hash"
        real_job_id = f"{job_id}_{hash_}"
        mock_hook.return_value.insert_job.return_value = MagicMock(job_id=real_job_id, error_result=False)
        with pytest.raises(TaskDeferred) as exc:
            ti.task.execute(MagicMock())

        assert isinstance(exc.value.trigger, BigQueryValueCheckTrigger), (
            "Trigger is not a BigQueryValueCheckTrigger"
        )

    @pytest.mark.db_test
    @mock.patch("airflow.providers.google.cloud.operators.bigquery.BigQueryValueCheckOperator.defer")
    @mock.patch("airflow.providers.google.cloud.operators.bigquery.BigQueryValueCheckOperator.check_value")
    @mock.patch("airflow.providers.google.cloud.operators.bigquery.BigQueryHook")
    def test_bigquery_value_check_operator_async_finish_before_deferred(
        self, mock_hook, mock_check_value, mock_defer, create_task_instance_of_operator
    ):
        job_id = "123456"
        hash_ = "hash"
        real_job_id = f"{job_id}_{hash_}"

        mocked_job = MagicMock(job_id=real_job_id, error_result=False)
        mocked_job.result.return_value = iter([(1, 2, 3)])  # mock rows generator
        mock_hook.return_value.insert_job.return_value = mocked_job
        mock_hook.return_value.insert_job.return_value.running.return_value = False

        ti = create_task_instance_of_operator(
            BigQueryValueCheckOperator,
            dag_id="dag_id",
            task_id="check_value",
            sql="SELECT COUNT(*) FROM Any",
            pass_value=2,
            use_legacy_sql=True,
            deferrable=True,
        )

        ti.task.execute(MagicMock())
        assert not mock_defer.called
        mock_check_value.assert_called_once_with((1, 2, 3))

    @pytest.mark.db_test
    @mock.patch("airflow.providers.google.cloud.operators.bigquery.BigQueryHook")
    def test_bigquery_value_check_operator_async_finish_with_error_before_deferred(
        self, mock_hook, create_task_instance_of_operator
    ):
        job_id = "123456"
        hash_ = "hash"
        real_job_id = f"{job_id}_{hash_}"

        mock_hook.return_value.insert_job.return_value = MagicMock(job_id=real_job_id, error_result=True)
        mock_hook.return_value.insert_job.return_value.running.return_value = False

        ti = create_task_instance_of_operator(
            BigQueryValueCheckOperator,
            dag_id="dag_id",
            task_id="check_value",
            sql="SELECT COUNT(*) FROM Any",
            pass_value=2,
            use_legacy_sql=True,
            deferrable=True,
        )

        with pytest.raises(AirflowException) as exc:
            ti.task.execute(MagicMock())

        assert str(exc.value) == f"BigQuery job {real_job_id} failed: True"

    @pytest.mark.parametrize(
        "kwargs, expected",
        [
            ({"sql": "SELECT COUNT(*) from Any"}, "missing keyword argument 'pass_value'"),
            ({"pass_value": "Any"}, "missing keyword argument 'sql'"),
        ],
    )
    def test_bigquery_value_check_missing_param(self, kwargs, expected):
        """
        Assert the exception if require param not pass to BigQueryValueCheckOperator with deferrable=True
        """
        with pytest.raises((TypeError, AirflowException)) as missing_param:
            BigQueryValueCheckOperator(deferrable=True, **kwargs)
        assert missing_param.value.args[0] == expected

    def test_bigquery_value_check_empty(self):
        """
        Assert the exception if require param not pass to BigQueryValueCheckOperator with deferrable=True
        """
        expected, expected1 = (
            "missing keyword arguments 'sql', 'pass_value'",
            "missing keyword arguments 'pass_value', 'sql'",
        )
        with pytest.raises((TypeError, AirflowException)) as missing_param:
            BigQueryValueCheckOperator(deferrable=True, kwargs={})
        assert missing_param.value.args[0] in (expected, expected1)

    def test_bigquery_value_check_project_id(self):
        operator = BigQueryValueCheckOperator(
            task_id="check_value",
            sql="SELECT COUNT(*) FROM Any",
            pass_value=2,
            use_legacy_sql=False,
            project_id=TEST_JOB_PROJECT_ID,
        )

        assert operator.project_id == TEST_JOB_PROJECT_ID

    def test_bigquery_value_check_operator_execute_complete_success(self):
        """Tests response message in case of success event"""
        operator = BigQueryValueCheckOperator(
            task_id="check_value",
            sql="SELECT COUNT(*) FROM Any",
            pass_value=2,
            use_legacy_sql=False,
            deferrable=True,
        )

        assert (
            operator.execute_complete(context=None, event={"status": "success", "message": "Job completed!"})
            is None
        )

    def test_bigquery_value_check_operator_execute_complete_failure(self):
        """Tests that an AirflowException is raised in case of error event"""
        operator = BigQueryValueCheckOperator(
            task_id="check_value",
            sql="SELECT COUNT(*) FROM Any",
            pass_value=2,
            use_legacy_sql=False,
            deferrable=True,
        )

        with pytest.raises(AirflowException):
            operator.execute_complete(
                context=None, event={"status": "error", "message": "test failure message"}
            )

    @mock.patch("airflow.providers.google.cloud.operators.bigquery.BigQueryHook")
    @mock.patch("airflow.providers.google.cloud.hooks.bigquery.BigQueryJob")
    def test_encryption_configuration_deferrable_mode(self, mock_job, mock_hook):
        encryption_configuration = {
            "kmsKeyName": "projects/PROJECT/locations/LOCATION/keyRings/KEY_RING/cryptoKeys/KEY",
        }

        mock_job.result.return_value.to_dataframe.return_value = pd.DataFrame(
            {
                "check_name": ["row_count_check"],
                "check_result": [1],
            }
        )
        mock_hook.return_value.insert_job.return_value = mock_job
        mock_hook.return_value.project_id = TEST_GCP_PROJECT_ID

        operator = BigQueryValueCheckOperator(
            task_id="TASK_ID",
            encryption_configuration=encryption_configuration,
            location=TEST_DATASET_LOCATION,
            pass_value=2,
            sql=f"SELECT COUNT(*) FROM {TEST_DATASET}.{TEST_TABLE_ID}",
            deferrable=True,
        )
        with pytest.raises(TaskDeferred):
            operator.execute(MagicMock())
        mock_hook.return_value.insert_job.assert_called_with(
            configuration={
                "query": {
                    "query": f"""SELECT COUNT(*) FROM {TEST_DATASET}.{TEST_TABLE_ID}""",
                    "useLegacySql": True,
                    "destinationEncryptionConfiguration": encryption_configuration,
                }
            },
            project_id=TEST_GCP_PROJECT_ID,
            location=TEST_DATASET_LOCATION,
            job_id="",
            nowait=True,
        )


@pytest.mark.db_test
class TestBigQueryColumnCheckOperator:
    @pytest.mark.parametrize(
        "check_type, check_value, check_result",
        [
            ("equal_to", 0, 0),
            ("greater_than", 0, 1),
            ("less_than", 0, -1),
            ("geq_to", 0, 1),
            ("geq_to", 0, 0),
            ("leq_to", 0, 0),
            ("leq_to", 0, -1),
        ],
    )
    @mock.patch("airflow.providers.google.cloud.operators.bigquery._BigQueryHookWithFlexibleProjectId")
    @mock.patch("airflow.providers.google.cloud.hooks.bigquery.BigQueryJob")
    def test_bigquery_column_check_operator_succeeds(
        self, mock_job, mock_hook, check_type, check_value, check_result, create_task_instance_of_operator
    ):
        mock_job.result.return_value.to_dataframe.return_value = pd.DataFrame(
            {"col_name": ["col1"], "check_type": ["min"], "check_result": [check_result]}
        )
        mock_hook.return_value.insert_job.return_value = mock_job

        ti = create_task_instance_of_operator(
            BigQueryColumnCheckOperator,
            dag_id="dag_id",
            task_id="check_column_succeeds",
            table=TEST_TABLE_ID,
            use_legacy_sql=False,
            column_mapping={
                "col1": {"min": {check_type: check_value}},
            },
        )
        ti.task.execute(MagicMock())

    @pytest.mark.parametrize(
        "check_type, check_value, check_result",
        [
            ("equal_to", 0, 1),
            ("greater_than", 0, -1),
            ("less_than", 0, 1),
            ("geq_to", 0, -1),
            ("leq_to", 0, 1),
        ],
    )
    @mock.patch("airflow.providers.google.cloud.operators.bigquery._BigQueryHookWithFlexibleProjectId")
    @mock.patch("airflow.providers.google.cloud.hooks.bigquery.BigQueryJob")
    def test_bigquery_column_check_operator_fails(
        self, mock_job, mock_hook, check_type, check_value, check_result, create_task_instance_of_operator
    ):
        mock_job.result.return_value.to_dataframe.return_value = pd.DataFrame(
            {"col_name": ["col1"], "check_type": ["min"], "check_result": [check_result]}
        )
        mock_hook.return_value.insert_job.return_value = mock_job

        ti = create_task_instance_of_operator(
            BigQueryColumnCheckOperator,
            dag_id="dag_id",
            task_id="check_column_fails",
            table=TEST_TABLE_ID,
            use_legacy_sql=False,
            column_mapping={
                "col1": {"min": {check_type: check_value}},
            },
        )
        with pytest.raises(AirflowException):
            ti.task.execute(MagicMock())

    @pytest.mark.parametrize(
        "check_type, check_value, check_result",
        [
            ("equal_to", 0, 0),
            ("greater_than", 0, 1),
            ("less_than", 0, -1),
        ],
    )
    @mock.patch("airflow.providers.google.cloud.operators.bigquery._BigQueryHookWithFlexibleProjectId")
    @mock.patch("airflow.providers.google.cloud.hooks.bigquery.BigQueryJob")
    def test_encryption_configuration(self, mock_job, mock_hook, check_type, check_value, check_result):
        encryption_configuration = {
            "kmsKeyName": "projects/PROJECT/locations/LOCATION/keyRings/KEY_RING/cryptoKeys/KEY",
        }

        mock_job.result.return_value.to_dataframe.return_value = pd.DataFrame(
            {"col_name": ["col1"], "check_type": ["min"], "check_result": [check_result]}
        )
        mock_hook.return_value.insert_job.return_value = mock_job
        mock_hook.return_value.project_id = TEST_GCP_PROJECT_ID

        operator = BigQueryColumnCheckOperator(
            task_id="TASK_ID",
            encryption_configuration=encryption_configuration,
            table=f"{TEST_DATASET}.{TEST_TABLE_ID}",
            column_mapping={"col1": {"min": {check_type: check_value}}},
            location=TEST_DATASET_LOCATION,
        )

        operator.execute(MagicMock())
        mock_hook.return_value.insert_job.assert_called_with(
            configuration={
                "query": {
                    "query": f"""SELECT col_name, check_type, check_result FROM (
        SELECT 'col1' AS col_name, 'min' AS check_type, col1_min AS check_result
        FROM (SELECT MIN(col1) AS col1_min FROM {TEST_DATASET}.{TEST_TABLE_ID} ) AS sq
    ) AS check_columns""",
                    "useLegacySql": True,
                    "destinationEncryptionConfiguration": encryption_configuration,
                }
            },
            project_id=TEST_GCP_PROJECT_ID,
            location=TEST_DATASET_LOCATION,
            job_id="",
            nowait=False,
        )


class TestBigQueryTableCheckOperator:
    @mock.patch("airflow.providers.google.cloud.operators.bigquery._BigQueryHookWithFlexibleProjectId")
    @mock.patch("airflow.providers.google.cloud.hooks.bigquery.BigQueryJob")
    def test_encryption_configuration(self, mock_job, mock_hook):
        encryption_configuration = {
            "kmsKeyName": "projects/PROJECT/locations/LOCATION/keyRings/KEY_RING/cryptoKeys/KEY",
        }

        mock_job.result.return_value.to_dataframe.return_value = pd.DataFrame(
            {
                "check_name": ["row_count_check"],
                "check_result": [1],
            }
        )
        mock_hook.return_value.insert_job.return_value = mock_job
        mock_hook.return_value.project_id = TEST_GCP_PROJECT_ID

        check_statement = "COUNT(*) = 1"
        operator = BigQueryTableCheckOperator(
            task_id="TASK_ID",
            table="test_table",
            checks={"row_count_check": {"check_statement": check_statement}},
            encryption_configuration=encryption_configuration,
            location=TEST_DATASET_LOCATION,
        )

        operator.execute(MagicMock())
        mock_hook.return_value.insert_job.assert_called_with(
            configuration={
                "query": {
                    "query": f"""SELECT check_name, check_result FROM (
    SELECT 'row_count_check' AS check_name, MIN(row_count_check) AS check_result
    FROM (SELECT CASE WHEN {check_statement} THEN 1 ELSE 0 END AS row_count_check
          FROM test_table ) AS sq
    ) AS check_table""",
                    "useLegacySql": True,
                    "destinationEncryptionConfiguration": encryption_configuration,
                }
            },
            project_id=TEST_GCP_PROJECT_ID,
            location=TEST_DATASET_LOCATION,
            job_id="",
            nowait=False,
        )

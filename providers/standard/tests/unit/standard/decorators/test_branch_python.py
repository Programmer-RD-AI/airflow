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

import pytest

from airflow.decorators import task
from airflow.utils.state import State

from tests_common.test_utils.version_compat import AIRFLOW_V_3_0_1

if AIRFLOW_V_3_0_1:
    from airflow.exceptions import DownstreamTasksSkipped

pytestmark = pytest.mark.db_test


class TestBranchPythonDecoratedOperator:
    # when run in "Parallel" test run environment, sometimes this test runs for a long time
    # because creating virtualenv and starting new Python interpreter creates a lot of IO/contention
    # possibilities. So we are increasing the timeout for this test to 3x of the default timeout
    @pytest.mark.execution_timeout(180)
    @pytest.mark.parametrize(
        ["branch_task_name", "skipped_task_name"], [("task_1", "task_2"), ("task_2", "task_1")]
    )
    def test_branch_one(self, dag_maker, branch_task_name, skipped_task_name):
        @task
        def dummy_f():
            pass

        @task
        def task_1():
            pass

        @task
        def task_2():
            pass

        @task.branch(task_id="branching")
        def branch_operator():
            return branch_task_name

        with dag_maker():
            branchoperator = branch_operator()
            df = dummy_f()
            task_1 = task_1()
            task_2 = task_2()

            df.set_downstream(branchoperator)
            branchoperator.set_downstream(task_1)
            branchoperator.set_downstream(task_2)

        dr = dag_maker.create_dagrun()
        dag_maker.run_ti("dummy_f", dr)
        if AIRFLOW_V_3_0_1:
            with pytest.raises(DownstreamTasksSkipped) as exc_info:
                dag_maker.run_ti("branching", dr)
            assert exc_info.value.tasks == [(skipped_task_name, -1)]
        else:
            dag_maker.run_ti("branching", dr)
            dag_maker.run_ti("task_1", dr)
            dag_maker.run_ti("task_2", dr)
            tis = dr.get_task_instances()

            for ti in tis:
                if ti.task_id == "dummy_f":
                    assert ti.state == State.SUCCESS
                if ti.task_id == "branching":
                    assert ti.state == State.SUCCESS

                if ti.task_id == "task_1" and branch_task_name == "task_1":
                    assert ti.state == State.SUCCESS
                elif ti.task_id == "task_1":
                    assert ti.state == State.SKIPPED

                if ti.task_id == "task_2" and branch_task_name == "task_2":
                    assert ti.state == State.SUCCESS
                elif ti.task_id == "task_2":
                    assert ti.state == State.SKIPPED

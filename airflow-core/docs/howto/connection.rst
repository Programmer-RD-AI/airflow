 .. Licensed to the Apache Software Foundation (ASF) under one
    or more contributor license agreements.  See the NOTICE file
    distributed with this work for additional information
    regarding copyright ownership.  The ASF licenses this file
    to you under the Apache License, Version 2.0 (the
    "License"); you may not use this file except in compliance
    with the License.  You may obtain a copy of the License at

 ..   http://www.apache.org/licenses/LICENSE-2.0

 .. Unless required by applicable law or agreed to in writing,
    software distributed under the License is distributed on an
    "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
    KIND, either express or implied.  See the License for the
    specific language governing permissions and limitations
    under the License.

Managing Connections
====================

.. seealso::

  For an overview of hooks and connections, see :doc:`/authoring-and-scheduling/connections`.

Airflow's :class:`~airflow.sdk.Connection` object is used for storing credentials and other information necessary for connecting to external services.

Connections may be defined in the following ways:

  - in :ref:`environment variables <environment_variables_connections>`
  - in an external :doc:`/security/secrets/secrets-backend/index`
  - in the :ref:`Airflow metadata database <connections-in-database>`
    (using the :ref:`CLI <connection/cli>` or :ref:`web UI <creating_connection_ui>`)

.. _environment_variables_connections:

Storing connections in environment variables
--------------------------------------------

Airflow connections may be defined in environment variables.

The naming convention is :envvar:`AIRFLOW_CONN_{CONN_ID}`, all uppercase (note the single underscores surrounding ``CONN``).  So if your connection id is ``my_prod_db`` then the variable name should be ``AIRFLOW_CONN_MY_PROD_DB``.

The value can be either JSON or Airflow's URI format.

.. _connection-serialization-json-example:

JSON format example
^^^^^^^^^^^^^^^^^^^

.. versionadded:: 2.3.0

If serializing with JSON:

.. code-block:: bash

    export AIRFLOW_CONN_MY_PROD_DATABASE='{
        "conn_type": "my-conn-type",
        "login": "my-login",
        "password": "my-password",
        "host": "my-host",
        "port": 1234,
        "schema": "my-schema",
        "extra": {
            "param1": "val1",
            "param2": "val2"
        }
    }'

Generating a JSON connection representation
"""""""""""""""""""""""""""""""""""""""""""

.. versionadded:: 2.8.0


To make connection JSON generation easier, the :py:class:`~airflow.models.connection.Connection` class has a
convenience property :py:meth:`~airflow.models.connection.Connection.as_json`. It can be used like so:

.. code-block:: pycon

    >>> from airflow.sdk import Connection
    >>> c = Connection(
    ...     conn_id="some_conn",
    ...     conn_type="mysql",
    ...     description="connection description",
    ...     host="myhost.com",
    ...     login="myname",
    ...     password="mypassword",
    ...     extra={"this_param": "some val", "that_param": "other val*"},
    ... )
    >>> print(f"AIRFLOW_CONN_{c.conn_id.upper()}='{c.as_json()}'")
    AIRFLOW_CONN_SOME_CONN='{"conn_type": "mysql", "description": "connection description", "host": "myhost.com", "login": "myname", "password": "mypassword", "extra": {"this_param": "some val", "that_param": "other val*"}}'

In addition, same approach could be used to convert Connection from URI format to JSON format

.. code-block:: pycon

    >>> from airflow.sdk import Connection
    >>> c = Connection(
    ...     conn_id="awesome_conn",
    ...     description="Example Connection",
    ...     uri="aws://AKIAIOSFODNN7EXAMPLE:wJalrXUtnFEMI%2FK7MDENG%2FbPxRfiCYEXAMPLEKEY@/?__extra__=%7B%22region_name%22%3A+%22eu-central-1%22%2C+%22config_kwargs%22%3A+%7B%22retries%22%3A+%7B%22mode%22%3A+%22standard%22%2C+%22max_attempts%22%3A+10%7D%7D%7D",
    ... )
    >>> print(f"AIRFLOW_CONN_{c.conn_id.upper()}='{c.as_json()}'")
    AIRFLOW_CONN_AWESOME_CONN='{"conn_type": "aws", "description": "Example Connection", "host": "", "login": "AKIAIOSFODNN7EXAMPLE", "password": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY", "schema": "", "extra": {"region_name": "eu-central-1", "config_kwargs": {"retries": {"mode": "standard", "max_attempts": 10}}}}'


URI format example
^^^^^^^^^^^^^^^^^^

If serializing with Airflow URI:

.. code-block:: bash

    export AIRFLOW_CONN_MY_PROD_DATABASE='my-conn-type://login:password@host:port/schema?param1=val1&param2=val2'

See :ref:`Connection URI format <connection-uri-format>` for more details on how to generate the a valid URI.

Visibility in UI and CLI
^^^^^^^^^^^^^^^^^^^^^^^^^

Connections defined through environment variables are **not displayed** in the Airflow UI or listed using ``airflow connections list``.

This is because these connections are **resolved dynamically at runtime**, typically on the **worker** process executing your task. They are not stored in the metadata database or loaded in the webserver or scheduler environment.

This supports secure deployment patterns where environment-based secrets (e.g. via ``.env`` files, Docker, or Kubernetes secrets) are injected only into runtime components like workers — and not into components exposed to users, like the webserver.

If you need connections to appear in the UI for visibility or editing, define them using the metadata database instead.


Storing connections in a Secrets Backend
----------------------------------------

You can store Airflow connections in external secrets backends like HashiCorp Vault, AWS SSM Parameter Store, and other such services. For more details see :doc:`/security/secrets/secrets-backend/index`.

.. _connections-in-database:

Storing connections in the database
-----------------------------------
.. seealso::

    Connections can alternatively be stored in :ref:`environment variables <environment_variables_connections>` or an :doc:`external secrets backend </security/secrets/secrets-backend/index>` such as HashiCorp Vault, AWS SSM Parameter Store, etc.

When storing connections in the database, you may manage them using either the web UI or the Airflow CLI.


.. _creating_connection_ui:

Creating a Connection with the UI
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Open the ``Admin->Connections`` section of the UI. Click the ``Add Connection`` link
to create a new connection.

.. image:: ../img/ui-dark/connection_create.png

1. Fill in the ``Connection Id`` field with the desired connection ID. It is
   recommended that you use lower-case characters and separate words with
   underscores.
2. Choose the connection type with the ``Connection Type`` field.
3. Fill in the remaining fields. See
   :ref:`manage-connections-connection-types` for a description of the fields
   belonging to the different connection types.
4. Click the ``Save`` button to create the connection.

.. _editing_connection_ui:

Editing a Connection with the UI
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Open the ``Admin->Connections`` section of the UI. Click the pencil icon next
to the connection you wish to edit in the connection list.

.. image:: ../img/ui-dark/connection_edit.png

Modify the connection properties and click the ``Save`` button to save your
changes.

.. _connection/cli:

Creating a Connection from the CLI
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

You may add a connection to the database from the CLI.

You can add a connection using JSON format (from version 2.3.0):

.. code-block:: bash

    airflow connections add 'my_prod_db' \
        --conn-json '{
            "conn_type": "my-conn-type",
            "login": "my-login",
            "password": "my-password",
            "host": "my-host",
            "port": 1234,
            "schema": "my-schema",
            "extra": {
                "param1": "val1",
                "param2": "val2"
            }
        }'

Alternatively you may use Airflow' Connection URI format (see :ref:`Generating a Connection URI <generating_connection_uri>`).

.. code-block:: bash

    airflow connections add 'my_prod_db' \
        --conn-uri '<conn-type>://<login>:<password>@<host>:<port>/<schema>?param1=val1&param2=val2&...'

Lastly, you may also specify each parameter individually:

.. code-block:: bash

    airflow connections add 'my_prod_db' \
        --conn-type 'my-conn-type' \
        --conn-login 'login' \
        --conn-password 'password' \
        --conn-host 'host' \
        --conn-port 'port' \
        --conn-schema 'schema' \
        ...

Exporting connections to file
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

You can export to file connections stored in the database (e.g. for migrating connections from one environment to another).  See :ref:`Exporting Connections <cli-export-connections>` for usage.


Security of connections in the database
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

For connections stored in the Airflow metadata database, Airflow uses `Fernet <https://github.com/fernet/spec/>`__ to encrypt password and other potentially sensitive data.  It guarantees that without the encryption password, Connection
Passwords cannot be manipulated or read without the key. For information on configuring Fernet, look at :ref:`security/fernet`.

Testing Connections
^^^^^^^^^^^^^^^^^^^
For security reasons, the test connection functionality is disabled by default across Airflow UI, API and CLI.

For more information on capabilities of users, see the documentation:
https://airflow.apache.org/docs/apache-airflow/stable/security/security_model.html#capabilities-of-authenticated-ui-users.
It is strongly advised to not enable the feature until you make sure that only
highly trusted UI/API users have "edit connection" permissions.

The availability of the
functionality can be controlled by the test_connection flag in
the core section of the Airflow configuration (airflow.cfg).
It can also be controlled by the environment variable
``AIRFLOW__CORE__TEST_CONNECTION``.

The following values are accepted for this config param:

* Disabled: Disables the test connection functionality and disables the Test Connection button in the UI. This is also the default value set in the Airflow configuration.
* Enabled: Enables the test connection functionality and activates the Test Connection button in the UI.
* Hidden: Disables the test connection functionality and hides the Test Connection button in UI.

After enabling Test Connection, it can be used from the
:ref:`create <creating_connection_ui>` or :ref:`edit <editing_connection_ui>` connection page in the UI, through calling
:doc:`Connections REST API </stable-rest-api-ref/>`, or running the ``airflow connections test`` :ref:`CLI command <cli>`.

.. warning::

    This feature won't be available for the connections residing in external secrets backends when using the
    Airflow UI or REST API.

To test a connection, Airflow calls the ``test_connection`` method from the associated hook class and reports the
results. It may happen that the connection type does not have any associated hook or the hook doesn't have the
``test_connection`` method implementation, in either case an error message will be displayed or functionality
will be disabled (if you are testing in the UI).

.. note::

    When testing in the Airflow UI, the test executes from the webserver so this feature is subject to network
    egress rules setup for your webserver.

.. note::

    If webserver & worker machines (if testing via the Airflow UI) or machines/pods (if testing via the
    Airflow CLI) have different libs or providers installed, test results *might* differ.


Custom connection types
^^^^^^^^^^^^^^^^^^^^^^^

Airflow allows the definition of custom connection types -- including modifications of the add/edit form
for the connections. Custom connection types are defined in community maintained providers, but you can
can also add a custom provider that adds custom connection types. See :doc:`apache-airflow-providers:index`
for description on how to add custom providers.

The custom connection types are defined via Hooks delivered by the providers. The Hooks can implement
methods defined in the protocol class :class:`~airflow.hooks.base_hook.DiscoverableHook`. Note that your
custom Hook should not derive from this class, this class is an example to document expectations
regarding about class fields and methods that your Hook might define. Another good example is
:py:class:`~airflow.providers.jdbc.hooks.jdbc.JdbcHook`.

By implementing those methods in your hooks and exposing them via ``connection-types`` array (and
deprecated ``hook-class-names``) in the provider meta-data, you can customize Airflow by:

* Adding custom connection types
* Adding automated Hook creation from the connection type
* Adding custom form widget to display and edit custom "extra" parameters in your connection URL
* Hiding fields that are not used for your connection
* Adding placeholders showing examples of how fields should be formatted

You can read more about details how to add custom providers in the :doc:`apache-airflow-providers:index`

Custom connection fields
------------------------

It is possible to add custom form fields in the connection add / edit views in the Airflow webserver.
Custom fields are stored in the ``Connection.extra`` field as JSON.  To add a custom field, implement
method :meth:`~BaseHook.get_connection_form_widgets`.  This method should return a dictionary. The keys
should be the string name of the field as it should be stored in the ``extra`` dict.  The values should
be inheritors of :class:`wtforms.fields.core.Field`.

Here's an example:

.. code-block:: python

    @staticmethod
    def get_connection_form_widgets() -> dict[str, Any]:
        """Returns connection widgets to add to connection form"""
        from flask_appbuilder.fieldwidgets import BS3TextFieldWidget
        from flask_babel import lazy_gettext
        from wtforms import StringField

        return {
            "workspace": StringField(lazy_gettext("Workspace"), widget=BS3TextFieldWidget()),
            "project": StringField(lazy_gettext("Project"), widget=BS3TextFieldWidget()),
        }

.. note:: Custom fields no longer need the ``extra__<conn type>__`` prefix

    Prior to Airflow 2.3, if you wanted a custom field in the UI, you had to prefix it with ``extra__<conn type>__``,
    and this is how its value would be stored in the ``extra`` dict.  From 2.3 onward, you no longer need to do this.

Method :meth:`~BaseHook.get_ui_field_behaviour` lets you customize behavior of both .  For example you can
hide or relabel a field (e.g. if it's unused or re-purposed) and you can add placeholder text.

An example:

.. code-block:: python

    @staticmethod
    def get_ui_field_behaviour() -> dict[str, Any]:
        """Returns custom field behaviour"""
        return {
            "hidden_fields": ["port", "host", "login", "schema"],
            "relabeling": {},
            "placeholders": {
                "password": "Asana personal access token",
                "workspace": "My workspace gid",
                "project": "My project gid",
            },
        }

.. note::

    If you want to add a form placeholder for an ``extra`` field whose name conflicts with a standard connection attribute (i.e. login, password, host, scheme, port, extra) then
    you must prefix it with ``extra__<conn type>__``.  E.g. ``extra__myservice__password``.

Take a look at providers for examples of what you can do, for example :py:class:`~airflow.providers.jdbc.hooks.jdbc.JdbcHook`
and :py:class:`~airflow.providers.asana.hooks.jdbc.AsanaHook` both make use of this feature.

.. note:: Deprecated ``hook-class-names``

   Prior to Airflow 2.2.0, the connections in providers have been exposed via ``hook-class-names`` array
   in provider's meta-data. However, this has proven to be inefficient when using individual hooks
   in workers, and the ``hook-class-names`` array is now replaced by the ``connection-types`` array. Until
   provider supports Airflow below 2.2.0, both ``connection-types`` and ``hook-class-names`` should be
   present. Automated checks during CI build will verify consistency of those two arrays.

.. _connection-uri-format:

URI format
----------

.. note::

    From version 2.3.0 you can serialize connections with JSON instead.  See :ref:`example <connection-serialization-json-example>`.

For historical reasons, Airflow has a special URI format that can be used for serializing a Connection object to a string value.

In general, Airflow's URI format looks like the following:

.. code-block::

    my-conn-type://my-login:my-password@my-host:5432/my-schema?param1=val1&param2=val2

The above URI would produce a ``Connection`` object equivalent to the following:

.. code-block:: python

    Connection(
        conn_id="",
        conn_type="my_conn_type",
        description=None,
        login="my-login",
        password="my-password",
        host="my-host",
        port=5432,
        schema="my-schema",
        extra=json.dumps(dict(param1="val1", param2="val2")),
    )

.. _generating_connection_uri:

Generating a connection URI
^^^^^^^^^^^^^^^^^^^^^^^^^^^

To make connection URI generation easier, the :py:class:`~airflow.models.connection.Connection` class has a
convenience method :py:meth:`~airflow.models.connection.Connection.get_uri`.  It can be used like so:

.. code-block:: pycon

    >>> import json
    >>> from airflow.sdk import Connection
    >>> c = Connection(
    ...     conn_id="some_conn",
    ...     conn_type="mysql",
    ...     description="connection description",
    ...     host="myhost.com",
    ...     login="myname",
    ...     password="mypassword",
    ...     extra=json.dumps(dict(this_param="some val", that_param="other val*")),
    ... )
    >>> print(f"AIRFLOW_CONN_{c.conn_id.upper()}='{c.get_uri()}'")
    AIRFLOW_CONN_SOME_CONN='mysql://myname:mypassword@myhost.com?this_param=some+val&that_param=other+val%2A'

.. note::

   The ``get_uri()`` method return the connection URI in Airflow format, **not** a SQLAlchemy-compatible URI. if you need a SQLAlchemy-compatible URI for database connections, use :attr:`~airflow.providers.common.sql.hooks.sql.DbApiHook.sqlalchemy_url` property instead.

Additionally, if you have created a connection, you can use ``airflow connections get`` command.

.. code-block:: console

    $ airflow connections get sqlite_default
    Id: 40
    Connection Id: sqlite_default
    Connection Type: sqlite
    Host: /tmp/sqlite_default.db
    Schema: null
    Login: null
    Password: null
    Port: null
    Is Encrypted: false
    Is Extra Encrypted: false
    Extra: {}
    URI: sqlite://%2Ftmp%2Fsqlite_default.db

.. _manage-connections-connection-types:

Handling of arbitrary dict in extra
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Some JSON structures cannot be urlencoded without loss.  For such JSON, ``get_uri``
will store the entire string under the url query param ``__extra__``.

For example:

.. code-block:: pycon

    >>> extra_dict = {"my_val": ["list", "of", "values"], "extra": {"nested": {"json": "val"}}}
    >>> c = Connection(
    ...     conn_type="scheme",
    ...     host="host/location",
    ...     schema="schema",
    ...     login="user",
    ...     password="password",
    ...     port=1234,
    ...     extra=json.dumps(extra_dict),
    ... )
    >>> uri = c.get_uri()
    >>> uri
    'scheme://user:password@host%2Flocation:1234/schema?__extra__=%7B%22my_val%22%3A+%5B%22list%22%2C+%22of%22%2C+%22values%22%5D%2C+%22extra%22%3A+%7B%22nested%22%3A+%7B%22json%22%3A+%22val%22%7D%7D%7D'


And we can verify that it returns the same dictionary:

.. code-block:: pycon

    >>> new_c = Connection(uri=uri)
    >>> new_c.extra_dejson == extra_dict
    True


But for the most common case of storing only key-value pairs, plain url encoding is used.

You can verify a URI is parsed correctly like so:

.. code-block:: pycon

    >>> from airflow.sdk import Connection

    >>> c = Connection(uri="my-conn-type://my-login:my-password@my-host:5432/my-schema?param1=val1&param2=val2")
    >>> print(c.login)
    my-login
    >>> print(c.password)
    my-password


Handling of special characters in connection params
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. note::

    Use the convenience method ``Connection.get_uri`` when generating a connection
    as described in section :ref:`Generating a Connection URI <generating_connection_uri>`.
    This section for informational purposes only.

Special handling is required for certain characters when building a URI manually.

For example if your password has a ``/``, this fails:

.. code-block:: pycon

    >>> c = Connection(uri="my-conn-type://my-login:my-pa/ssword@my-host:5432/my-schema?param1=val1&param2=val2")
    ValueError: invalid literal for int() with base 10: 'my-pa'

To fix this, you can encode with :func:`~urllib.parse.quote_plus`:

.. code-block:: pycon

    >>> c = Connection(uri="my-conn-type://my-login:my-pa%2Fssword@my-host:5432/my-schema?param1=val1&param2=val2")
    >>> print(c.password)
    my-pa/ssword

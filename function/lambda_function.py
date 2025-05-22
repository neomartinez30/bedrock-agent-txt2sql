import boto3
from time import sleep

# Initialize the Athena client
athena_client = boto3.client('athena')

def lambda_handler(event, context):
    print(event)

    def athena_query_handler(event):
        # Extracting the SQL query from the OpenAPI-compliant request
        query = event['requestBody']['query']
        print("the received QUERY:",  query)
        s3_output = 's3://athena-destination-store-neoathome/'  # Replace with your S3 bucket
        execution_id = execute_athena_query(query, s3_output)
        result = get_query_results(execution_id)
        return result

    def execute_athena_query(query, s3_output):
        response = athena_client.start_query_execution(
            QueryString=query,
            ResultConfiguration={'OutputLocation': s3_output}
        )
        return response['QueryExecutionId']

    def check_query_status(execution_id):
        response = athena_client.get_query_execution(QueryExecutionId=execution_id)
        return response['QueryExecution']['Status']['State']

    def get_query_results(execution_id):
        while True:
            status = check_query_status(execution_id)
            if status in ['SUCCEEDED', 'FAILED', 'CANCELLED']:
                break
            sleep(1)  # Polling interval

        if status == 'SUCCEEDED':
            raw_result = athena_client.get_query_results(QueryExecutionId=execution_id)
            # Format Athena results to match OpenAPI schema
            columns = [col['Label'] for col in raw_result['ResultSet']['ResultSetMetadata']['ColumnInfo']]
            rows = raw_result['ResultSet']['Rows'][1:]  # skip header row
            result_set = []
            for row in rows:
                values = [field.get('VarCharValue', None) for field in row['Data']]
                # Convert types for known columns
                formatted = {}
                for col, val in zip(columns, values):
                    if col == 'age' and val is not None:
                        formatted[col] = int(val)
                    elif col == 'billing_amount' and val is not None:
                        formatted[col] = float(val)
                    else:
                        formatted[col] = val
                result_set.append(formatted)
            return {'ResultSet': result_set}
        else:
            return {'error': f"Query failed with status '{status}'"}

    action_group = event.get('actionGroup')
    api_path = event.get('apiPath')

    print("api_path: ", api_path)

    result = ''
    response_code = 200


    if api_path == '/athenaQuery':
        result = athena_query_handler(event)
    else:
        response_code = 404
        result = {"error": f"Unrecognized api path: {action_group}::{api_path}"}

    response_body = {
        'application/json': {
            'body': result
        }
    }

    action_response = {
        'actionGroup': action_group,
        'apiPath': api_path,
        'httpMethod': event.get('httpMethod'),
        'httpStatusCode': response_code,
        'responseBody': response_body
    }

    api_response = {'messageVersion': '1.0', 'response': action_response}
    return api_response

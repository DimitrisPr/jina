import json
import os

import pytest
import yaml
from google.protobuf.json_format import MessageToJson

from jina import Document
from jina.jaml import JAML
from jina.optimizers import FlowOptimizer, MeanEvaluationCallback
from jina.optimizers import run_optimizer_cli
from jina.optimizers.flow_runner import SingleFlowRunner
from jina.parsers.optimizer import set_optimizer_parser

BEST_PARAMETERS = {
    'JINA_DUMMYCRAFTER_PARAM1': 0,
    'JINA_DUMMYCRAFTER_PARAM2': 1,
    'JINA_DUMMYCRAFTER_PARAM3': 1,
}


@pytest.fixture
def config(tmpdir):
    'tests/integration/optimizers/parameter.yml'
    os.environ['JINA_OPTIMIZER_WORKSPACE_DIR'] = str(tmpdir)
    os.environ['JINA_OPTIMIZER_OUTPUT_FILE'] = os.path.join(tmpdir, 'best_parameters.yml')
    yield
    del os.environ['JINA_OPTIMIZER_WORKSPACE_DIR']
    del os.environ['JINA_OPTIMIZER_OUTPUT_FILE']



def validate_result(result, tmpdir):
    result_path = os.path.join(tmpdir, 'best_parameters.yml')
    result.save_parameters(result_path)
    assert result.best_parameters == BEST_PARAMETERS
    assert yaml.load(open(result_path)) == BEST_PARAMETERS


def document_generator(num_doc):
    for _ in range(num_doc):
        doc = Document(content='hello')
        groundtruth_doc = Document(content='hello')
        yield doc, groundtruth_doc


def test_optimizer(tmpdir, config):
    eval_flow_runner = SingleFlowRunner(
        flow_yaml=os.path.join('tests', 'integration', 'optimizers', 'flow.yml'),
        documents=document_generator(10),
        request_size=1,
        execution_method='search',
    )
    opt = FlowOptimizer(
        flow_runner=eval_flow_runner,
        parameter_yaml=os.path.join('tests', 'integration', 'optimizers', 'parameter.yml'),
        evaluation_callback=MeanEvaluationCallback(),
        workspace_base_dir=str(tmpdir),
        n_trials=5,
    )
    result = opt.optimize_flow()
    validate_result(result, tmpdir)


def test_yaml(tmpdir, config):
    jsonlines_file = os.path.join(tmpdir, 'docs.jsonlines')
    optimizer_yaml = f'''!FlowOptimizer
version: 1
with:
  flow_runner: !SingleFlowRunner
    with:
      flow_yaml: {os.path.join('tests', 'integration', 'optimizers', 'flow.yml')}
      documents: {jsonlines_file}
      request_size: 1
      execution_method: 'search_lines'
      documents_parameter_name: 'filepath'
  evaluation_callback: !MeanEvaluationCallback {{}}
  parameter_yaml: {os.path.join('tests', 'integration', 'optimizers', 'parameter.yml')}
  workspace_base_dir: {tmpdir}
  n_trials: 5
'''
    documents = document_generator(10)
    with open(jsonlines_file, 'w') as f:
        for document, groundtruth_doc in documents:
            document.id = ""
            groundtruth_doc.id = ""
            json.dump(
                {
                    'document': json.loads(MessageToJson(document).replace('\n', '')),
                    'groundtruth': json.loads(MessageToJson(groundtruth_doc).replace('\n', '')),
                },
                f,
            )
            f.write('\n')

    optimizer = JAML.load(optimizer_yaml)
    result = optimizer.optimize_flow()
    validate_result(result, tmpdir)


@pytest.mark.parametrize('uses_output_file', (True, False))
def test_cli(tmpdir, config, uses_output_file):
    args = [
        '--uses',
        'tests/integration/optimizers/optimizer_conf.yml'
    ]
    output_file = os.path.join(tmpdir, 'best_parameters.yml')
    if uses_output_file:
        args.extend([
            '--output_file',
            output_file
        ])
    run_optimizer_cli(
        set_optimizer_parser().parse_args(args)
    )
    if uses_output_file:
        assert yaml.load(open(output_file)) == BEST_PARAMETERS

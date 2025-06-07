import os
import sys
import time
import asyncio
import zmq.asyncio

if sys.platform.startswith('win'):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)
sys.path.insert(0, root_dir)

from Backend.database import Database
from enum import IntEnum
from Agents import *
import zmq
import json
from dotenv import load_dotenv


load_dotenv()
cred_file = os.path.join(root_dir, 'firebase.json')
master_agent = None
db = Database(db_type='firestore', config=cred_file)


class OpStatus(IntEnum):
    SUCCESS = 0
    INVALID_FIELD = 1
    DOCUMENT_NOT_FOUND = 2
    EMPTY_DOCUMENT = 3
    OPERATION_CANCELLED = 4
    INVALID_INPUT = 5


def MasterAgent():
    global master_agent
    if master_agent is None:
        master_agent = AgentManager()
        master_agent.start()
    return master_agent


def GetCollection(collection_name):
    collections = db.get_collection(collection_name)
    if collections:
        return OpStatus.SUCCESS
    return OpStatus.DOCUMENT_NOT_FOUND


def CreateDocument(params):
    collection_name = params.get('collection_name')
    document_data = params.get('document_data')
    document_name = params.get('document_id')
    if not isinstance(document_data, dict):
        return ('document_data must be a dictionary', 400)
    if not collection_name:
        return OpStatus.DOCUMENT_NOT_FOUND
    if not isinstance(document_data, dict):
        return "Error: Document data must be a dictionary."

    try:
        doc_id = db.create_document(collection_name, document_data, document_name)
        return f"Success: Document added successfully with name: {doc_id}"
    except Exception as e:
        return f"Error: Error adding document: {str(e)}"


def ReadDocument(params):
    collection_name = params.get('collection_name')
    document_id = params.get('document_id')
    try:
        if not document_id or document_id.strip() == "":  # Multiple docs
            docs = db.read_document(collection_name)
            return docs, 200
        doc = db.read_document(collection_name.strip(), document_id.strip())
        if doc:
            return doc, 200
        else:
            return {"error": f"Document '{document_id}' does not exist"}, 404
    except Exception as e:
        return {"error": f"Error reading document(s): {str(e)}"}, 500


def GetDocuments(collection_name):
    try:
        docs = db.read_document(collection_name)
        if not docs:
            return 'Error: No documents found in the collection.'
        documents = [str(doc) for doc in docs.values()]
        return "\n".join(documents)
    except Exception as e:
        return f'Error: Error getting documents: {str(e)}'


def UpdateDocument(params):
    collection_name = params.get('collection_name')
    document_id = params.get('document_id')
    document_data = params.get('document_data')
    merge = params.get('merge', True)
    add_section = params.get('add_section', False)
    section_key = params.get('section_key', None)
    section_data = params.get('section_data', None)
    
    if not collection_name or not document_id:
        return 'Error: Collection name and document ID cannot be empty.'

    if document_data is None and not add_section:
        return 'Error: No data provided for update.'

    try:
        # If add_section is True, add or update the specified section
        if add_section and section_key and isinstance(section_data, dict):
            existing_data = db.read_document(collection_name, document_id) or {}
            nested_data = existing_data.get(section_key, {})
            if isinstance(nested_data, dict):
                nested_data.update(section_data)
            else:
                nested_data = section_data
            document_data = {section_key: nested_data}
        updated = db.update_document(collection_name, document_id, document_data, merge=merge)
        if updated:
            return f'Success: Document "{document_id}" updated successfully'
        else:
            return f'Error: Document "{document_id}" does not exist'
    except Exception as e:
        return f'Error: Error updating document: {str(e)}'


def DeleteDocument(params):
    collection_name = params.get('collection_name')
    document_id = params.get('document_id')
    try:
        deleted = db.delete_document(collection_name, document_id)
        if deleted:
            return 'Success: Document deleted successfully.'
        else:
            return f'Error: Document "{document_id}" does not exist.'
    except Exception as e:
        return f'Error: Error deleting document: {str(e)}'


def StartAgent(params):
    agent_type_str = params.get('agent_type')
    try:
        manager = MasterAgent()
        agent_type = None
        for member in AgentType:
            if member.value.lower() == agent_type_str.lower():
                agent_type = member
                break

        if agent_type is None:
            return f"Invalid agent type: {agent_type_str}", 400

        agent = manager.Create(agent_type=agent_type)
        manager.Start(agent.agent_id)
        
        # Wait a short moment for the process to start and get its PID
        time.sleep(0.1)
        
        process = manager.processes.get(agent.agent_id)
        return {
            'agent_id': agent.agent_id,
            'type': agent_type_str,
            'status': manager.agents[agent.agent_id]['status'],
            'port': COMMAND_PORT + agent.agent_id,
            'pid': process.pid if process else None,
            'alive': process.is_alive() if process else False
        }, 201
    except Exception as e:
        return f"Agent creation failed: {str(e)}", 500


def GetAgents(params):
    manager = MasterAgent()
    agents = []
    for agent_id, agent_info in manager.agents.items():
        try:
            process = manager.processes.get(agent_id)
            agents.append({
                'id': agent_id,
                'type': agent_info['type'],
                'alive': process.is_alive() if process else False,
                'status': agent_info['status'],
                'port': COMMAND_PORT + agent_id,
                'pid': process.pid if process else None
            })
        except Exception as e:
            # Skip agents that can't be accessed
            continue
    return agents, 200


def StopAgent(params):
    agent_id = params.get('agent_id')
    try:
        manager = MasterAgent()
        manager.Stop(agent_id)
        return f"Agent {agent_id} stopped", 200
    except Exception as e:
        return f"Failed to stop agent: {str(e)}", 500


def AgentCommand(params):
    if not params or 'agent_id' not in params or 'command' not in params:
            return {
                'status': 'error',
                'message': 'Missing required fields: agent_id and command'
            }, 400
    try:
        agent_id = params.get('agent_id')
        command = params.get('command')
        return master_agent.SendAgentCommand(agent_id, command)
    except Exception as e:
        return {
            'status': 'error',
            'message': f'Error sending command: {str(e)}'
        }, 500


async def ProcessCommand(command, params):
    """Process commands asynchronously"""
    func = operations.get(command.lower())
    if func:
        # If the function is async, await it
        if asyncio.iscoroutinefunction(func):
            return await func(params)
        # Otherwise, run it in a thread pool to avoid blocking
        return await asyncio.to_thread(func, params)
    else:
        return f'Error: Unknown command "{command}".'


operations = {
    'create': CreateDocument,
    'read': ReadDocument,
    'update': UpdateDocument,
    'delete': DeleteDocument,
    'status': lambda params: {'message': 'Server is online!'},
    'start_agent': StartAgent,
    'get_agents': GetAgents,
    'stop_agent': StopAgent,
    'agent_command': AgentCommand
}


async def Main():
    context = zmq.asyncio.Context()
    server = context.socket(zmq.REP)
    server.bind('tcp://0.0.0.0:5001')
    print('ZeroMQ server is running on port 5001...')

    try:
        while True:
            try:
                # Wait for a message
                message = await server.recv_json()
                command = message.get('command')
                params = message.get('params', {})

                if command == 'exit':
                    await server.send_json({'status': 'shutdown'})
                    break

                # Process the command
                response = await ProcessCommand(command, params)
                if isinstance(response, tuple) and len(response) == 2:
                    response_data = {
                        'data': response[0],
                        'status_code': response[1]
                    }
                else:
                    response_data = {
                        'data': response,
                        'status_code': 200
                    }
                await server.send_json(response_data)
            except zmq.error.Again:
                # This is a non-blocking recv timeout - just continue the loop
                # Don't try to send a response as we haven't received a message
                print("ZMQ receive timeout, continuing...")
                await asyncio.sleep(0.1)
                continue
            except (json.JSONDecodeError, KeyError) as e:
                # Only send an error response if we successfully received a message
                try:
                    await server.send_json({'error': f'Invalid request: {str(e)}'})
                except zmq.error.ZMQError:
                    print(f"Error sending response: {str(e)}")
            except Exception as e:
                # Only send an error response if we successfully received a message
                try:
                    await server.send_json({'error': f'Server error: {str(e)}'})
                except zmq.error.ZMQError:
                    print(f"Error in request processing: {str(e)}")
    except KeyboardInterrupt:
        print("\nShutting down server...")
    finally:
        server.close()
        context.term()


if __name__ == '__main__':
    asyncio.run(Main())
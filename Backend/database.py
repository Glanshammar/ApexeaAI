import os
from typing import Any, Dict, Optional, Union
import shutil

class FirestoreDB:
    def __init__(self, config: Optional[Union[Dict[str, Any], str]] = None):
        import firebase_admin
        from firebase_admin import credentials, firestore
        # Accept config as a string (cred_path) or dict
        if isinstance(config, str):
            cred_path = config
        else:
            cred_path = (config or {}).get('cred_path') if config else None
            if not cred_path:
                cred_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'credentials.json')
        if not firebase_admin._apps:
            if not os.path.exists(cred_path):
                print(f'Please place the {cred_path} in the same directory as this script.')
                cred_input = input('Enter the full path to the credentials file: ').strip()
                if os.path.exists(cred_input):
                    shutil.copy(cred_input, cred_path)
                    print(f'✅ Credentials file copied to {cred_path}')
                else:
                    raise FileNotFoundError(f'⚠️ File not found at {cred_input}. Please check the path and try again.')
            else:
                print('✅ Credentials found.')
            cred = credentials.Certificate(cred_path)
            firebase_admin.initialize_app(cred)
        self.db = firestore.client()

    def create_document(self, collection_name: str, document_data: dict, document_id: Optional[str] = None) -> str:
        collection_ref = self.db.collection(collection_name)
        if document_id is None:
            count_snapshot = collection_ref.get()
            document_id = str(len(count_snapshot))
        doc_ref = collection_ref.document(document_id)
        doc_ref.set(document_data)
        return document_id

    def read_document(self, collection_name: str, document_id: Optional[str] = None) -> Any:
        collection_ref = self.db.collection(collection_name)
        if not document_id:
            docs = collection_ref.stream()
            return {doc.id: doc.to_dict() for doc in docs}
        doc_ref = collection_ref.document(document_id)
        doc = doc_ref.get()
        if doc.exists:
            return doc.to_dict()
        else:
            return None

    def update_document(self, collection_name: str, document_id: str, document_data: dict, merge: bool = True) -> bool:
        collection_ref = self.db.collection(collection_name)
        doc_ref = collection_ref.document(document_id)
        if not doc_ref.get().exists:
            return False
        doc_ref.set(document_data, merge=merge)
        return True

    def delete_document(self, collection_name: str, document_id: str) -> bool:
        collection_ref = self.db.collection(collection_name)
        doc_ref = collection_ref.document(document_id)
        if doc_ref.get().exists:
            doc_ref.delete()
            return True
        return False

    def get_collection(self, collection_name: str):
        return [collection.id for collection in self.db.collections() if collection.id == collection_name]

class Database:
    def __init__(self, db_type: str = 'firestore', config: Optional[Union[Dict[str, Any], str]] = None):
        self.db_type = db_type
        self.config = config
        self._db = self._get_db_instance(db_type, self.config)

    def _get_db_instance(self, db_type: str, config: Optional[Union[Dict[str, Any], str]] = None):
        if db_type == 'firestore':
            return FirestoreDB(config)
        else:
            raise NotImplementedError(f"Database type '{db_type}' is not supported yet.")

    def create_document(self, *args, **kwargs):
        return self._db.create_document(*args, **kwargs)

    def read_document(self, *args, **kwargs):
        return self._db.read_document(*args, **kwargs)

    def update_document(self, *args, **kwargs):
        return self._db.update_document(*args, **kwargs)

    def delete_document(self, *args, **kwargs):
        return self._db.delete_document(*args, **kwargs)

    def get_collection(self, *args, **kwargs):
        return self._db.get_collection(*args, **kwargs)

    @classmethod
    def supported_types(cls):
        return ['firestore'] 
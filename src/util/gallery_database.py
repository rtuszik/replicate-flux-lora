import sqlite3
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from contextlib import contextmanager

from loguru import logger
from .output_handler import ProcessedOutput, OutputType


@dataclass
class GenerationRecord:
    id: str
    model_string: str
    model_category: str
    input_params: Dict[str, Any]
    created_at: datetime
    thumbnail_path: Optional[str] = None
    favorite: bool = False
    outputs: List[Dict[str, Any]] = None  # Serialized ProcessedOutput data


class GalleryDatabase:
    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()
        logger.info(f"GalleryDatabase initialized at {db_path}")

    def _init_database(self):
        """Initialize the database with required tables"""
        with self._get_connection() as conn:
            # Create generations table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS generations (
                    id TEXT PRIMARY KEY,
                    model_string TEXT NOT NULL,
                    model_category TEXT,
                    input_params TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    thumbnail_path TEXT,
                    favorite BOOLEAN DEFAULT FALSE
                )
            """)
            
            # Create generation_outputs table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS generation_outputs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    generation_id TEXT NOT NULL,
                    output_type TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    file_size INTEGER,
                    mime_type TEXT,
                    width INTEGER,
                    height INTEGER,
                    duration REAL,
                    metadata TEXT,
                    FOREIGN KEY (generation_id) REFERENCES generations(id) ON DELETE CASCADE
                )
            """)
            
            # Create model_schemas table for caching
            conn.execute("""
                CREATE TABLE IF NOT EXISTS model_schemas (
                    model_string TEXT PRIMARY KEY,
                    schema_data TEXT NOT NULL,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create indexes for performance
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_generations_created_at 
                ON generations(created_at)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_generations_model 
                ON generations(model_string)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_generations_category 
                ON generations(model_category)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_generations_favorite 
                ON generations(favorite)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_outputs_generation 
                ON generation_outputs(generation_id)
            """)
            
            conn.commit()

    @contextmanager
    def _get_connection(self):
        """Get a database connection with proper error handling"""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row  # Enable column access by name
        try:
            yield conn
        except Exception as e:
            conn.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            conn.close()

    def save_generation(self, 
                       generation_id: str,
                       model_string: str, 
                       model_category: str,
                       input_params: Dict[str, Any], 
                       outputs: List[ProcessedOutput],
                       thumbnail_path: Optional[str] = None) -> bool:
        """Save a generation and its outputs to the database"""
        try:
            with self._get_connection() as conn:
                # Insert generation record
                conn.execute("""
                    INSERT OR REPLACE INTO generations 
                    (id, model_string, model_category, input_params, thumbnail_path, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    generation_id,
                    model_string,
                    model_category,
                    json.dumps(input_params),
                    thumbnail_path,
                    datetime.now()
                ))
                
                # Delete existing outputs for this generation (in case of update)
                conn.execute("""
                    DELETE FROM generation_outputs WHERE generation_id = ?
                """, (generation_id,))
                
                # Insert output records
                for output in outputs:
                    conn.execute("""
                        INSERT INTO generation_outputs 
                        (generation_id, output_type, file_path, file_size, mime_type, 
                         width, height, duration, metadata)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        generation_id,
                        output.type.value,
                        output.file_path,
                        output.file_size,
                        output.mime_type,
                        output.width,
                        output.height,
                        output.duration,
                        json.dumps(output.metadata) if output.metadata else None
                    ))
                
                conn.commit()
                logger.info(f"Saved generation {generation_id} with {len(outputs)} outputs")
                return True
                
        except Exception as e:
            logger.error(f"Error saving generation {generation_id}: {e}")
            return False

    def get_generations(self, 
                       limit: int = 50, 
                       offset: int = 0,
                       filter_model: Optional[str] = None,
                       filter_category: Optional[str] = None,
                       favorites_only: bool = False,
                       sort_by: str = "created_at",
                       sort_order: str = "DESC") -> List[GenerationRecord]:
        """Get generations with optional filtering and pagination"""
        try:
            with self._get_connection() as conn:
                query = """
                    SELECT g.*, 
                           GROUP_CONCAT(go.output_type) as output_types,
                           COUNT(go.id) as output_count
                    FROM generations g
                    LEFT JOIN generation_outputs go ON g.id = go.generation_id
                    WHERE 1=1
                """
                params = []
                
                if filter_model:
                    query += " AND g.model_string LIKE ?"
                    params.append(f"%{filter_model}%")
                
                if filter_category:
                    query += " AND g.model_category = ?"
                    params.append(filter_category)
                
                if favorites_only:
                    query += " AND g.favorite = 1"
                
                query += f" GROUP BY g.id ORDER BY g.{sort_by} {sort_order} LIMIT ? OFFSET ?"
                params.extend([limit, offset])
                
                rows = conn.execute(query, params).fetchall()
                
                generations = []
                for row in rows:
                    # Get outputs for this generation
                    outputs = self._get_outputs_for_generation(conn, row['id'])
                    
                    generation = GenerationRecord(
                        id=row['id'],
                        model_string=row['model_string'],
                        model_category=row['model_category'] or 'unknown',
                        input_params=json.loads(row['input_params']),
                        created_at=datetime.fromisoformat(row['created_at']),
                        thumbnail_path=row['thumbnail_path'],
                        favorite=bool(row['favorite']),
                        outputs=outputs
                    )
                    generations.append(generation)
                
                return generations
                
        except Exception as e:
            logger.error(f"Error getting generations: {e}")
            return []

    def _get_outputs_for_generation(self, conn, generation_id: str) -> List[Dict[str, Any]]:
        """Get outputs for a specific generation"""
        rows = conn.execute("""
            SELECT * FROM generation_outputs 
            WHERE generation_id = ? 
            ORDER BY id
        """, (generation_id,)).fetchall()
        
        outputs = []
        for row in rows:
            output_data = {
                'id': row['id'],
                'type': row['output_type'],
                'file_path': row['file_path'],
                'file_size': row['file_size'],
                'mime_type': row['mime_type'],
                'width': row['width'],
                'height': row['height'],
                'duration': row['duration'],
                'metadata': json.loads(row['metadata']) if row['metadata'] else None
            }
            outputs.append(output_data)
        
        return outputs

    def get_generation_by_id(self, generation_id: str) -> Optional[GenerationRecord]:
        """Get a specific generation by ID"""
        generations = self.get_generations(limit=1, offset=0)
        
        try:
            with self._get_connection() as conn:
                row = conn.execute("""
                    SELECT * FROM generations WHERE id = ?
                """, (generation_id,)).fetchone()
                
                if not row:
                    return None
                
                outputs = self._get_outputs_for_generation(conn, generation_id)
                
                return GenerationRecord(
                    id=row['id'],
                    model_string=row['model_string'],
                    model_category=row['model_category'] or 'unknown',
                    input_params=json.loads(row['input_params']),
                    created_at=datetime.fromisoformat(row['created_at']),
                    thumbnail_path=row['thumbnail_path'],
                    rating=row['rating'],
                    notes=row['notes'] or '',
                    favorite=bool(row['favorite']),
                    outputs=outputs
                )
                
        except Exception as e:
            logger.error(f"Error getting generation {generation_id}: {e}")
            return None

    def search_generations(self, query: str, limit: int = 50) -> List[GenerationRecord]:
        """Search generations by prompt text or model name"""
        try:
            with self._get_connection() as conn:
                sql = """
                    SELECT g.*, 
                           GROUP_CONCAT(go.output_type) as output_types,
                           COUNT(go.id) as output_count
                    FROM generations g
                    LEFT JOIN generation_outputs go ON g.id = go.generation_id
                    WHERE g.model_string LIKE ? OR g.input_params LIKE ? OR g.notes LIKE ?
                    GROUP BY g.id
                    ORDER BY g.created_at DESC
                    LIMIT ?
                """
                
                search_term = f"%{query}%"
                rows = conn.execute(sql, (search_term, search_term, search_term, limit)).fetchall()
                
                generations = []
                for row in rows:
                    outputs = self._get_outputs_for_generation(conn, row['id'])
                    
                    generation = GenerationRecord(
                        id=row['id'],
                        model_string=row['model_string'],
                        model_category=row['model_category'] or 'unknown',
                        input_params=json.loads(row['input_params']),
                        created_at=datetime.fromisoformat(row['created_at']),
                        thumbnail_path=row['thumbnail_path'],
                        favorite=bool(row['favorite']),
                        outputs=outputs
                    )
                    generations.append(generation)
                
                return generations
                
        except Exception as e:
            logger.error(f"Error searching generations: {e}")
            return []

    def delete_generation(self, generation_id: str) -> bool:
        """Delete a generation and its outputs"""
        try:
            with self._get_connection() as conn:
                # Get file paths before deletion for cleanup
                output_rows = conn.execute("""
                    SELECT file_path FROM generation_outputs WHERE generation_id = ?
                """, (generation_id,)).fetchall()
                
                thumbnail_row = conn.execute("""
                    SELECT thumbnail_path FROM generations WHERE id = ?
                """, (generation_id,)).fetchone()
                
                # Delete from database (cascade will handle outputs)
                conn.execute("DELETE FROM generations WHERE id = ?", (generation_id,))
                conn.commit()
                
                # Clean up files
                for row in output_rows:
                    if row['file_path'] and os.path.exists(row['file_path']):
                        try:
                            os.remove(row['file_path'])
                        except Exception as e:
                            logger.warning(f"Could not delete file {row['file_path']}: {e}")
                
                if thumbnail_row and thumbnail_row['thumbnail_path']:
                    thumbnail_path = thumbnail_row['thumbnail_path']
                    if os.path.exists(thumbnail_path):
                        try:
                            os.remove(thumbnail_path)
                        except Exception as e:
                            logger.warning(f"Could not delete thumbnail {thumbnail_path}: {e}")
                
                logger.info(f"Deleted generation {generation_id}")
                return True
                
        except Exception as e:
            logger.error(f"Error deleting generation {generation_id}: {e}")
            return False

    def toggle_favorite(self, generation_id: str) -> bool:
        """Toggle favorite status of a generation"""
        try:
            with self._get_connection() as conn:
                conn.execute("""
                    UPDATE generations 
                    SET favorite = NOT favorite 
                    WHERE id = ?
                """, (generation_id,))
                conn.commit()
                
                logger.info(f"Toggled favorite for generation {generation_id}")
                return True
                
        except Exception as e:
            logger.error(f"Error toggling favorite for {generation_id}: {e}")
            return False


    def get_generation_count(self, filter_category: Optional[str] = None, favorites_only: bool = False) -> int:
        """Get total count of generations with optional filtering"""
        try:
            with self._get_connection() as conn:
                query = "SELECT COUNT(*) as count FROM generations g"
                params = []
                
                conditions = []
                if filter_category:
                    conditions.append("g.model_category = ?")
                    params.append(filter_category)
                
                if favorites_only:
                    conditions.append("g.favorite = 1")
                
                if conditions:
                    query += " WHERE " + " AND ".join(conditions)
                
                result = conn.execute(query, params).fetchone()
                return result['count'] if result else 0
                
        except Exception as e:
            logger.error(f"Error getting generation count: {e}")
            return 0

    def get_model_usage_stats(self) -> Dict[str, int]:
        """Get usage statistics by model"""
        try:
            with self._get_connection() as conn:
                rows = conn.execute("""
                    SELECT model_string, COUNT(*) as usage_count
                    FROM generations
                    GROUP BY model_string
                    ORDER BY usage_count DESC
                """).fetchall()
                
                return {row['model_string']: row['usage_count'] for row in rows}
                
        except Exception as e:
            logger.error(f"Error getting model usage stats: {e}")
            return {}

    def get_category_stats(self) -> Dict[str, int]:
        """Get usage statistics by category"""
        try:
            with self._get_connection() as conn:
                rows = conn.execute("""
                    SELECT model_category, COUNT(*) as usage_count
                    FROM generations
                    GROUP BY model_category
                    ORDER BY usage_count DESC
                """).fetchall()
                
                return {row['model_category']: row['usage_count'] for row in rows}
                
        except Exception as e:
            logger.error(f"Error getting category stats: {e}")
            return {}

    def sync_with_filesystem(self, output_dir: str) -> Dict[str, int]:
        """Synchronize database with filesystem"""
        stats = {"removed_records": 0, "removed_files": 0}
        
        try:
            with self._get_connection() as conn:
                # Find database entries with missing files
                rows = conn.execute("""
                    SELECT go.id, go.generation_id, go.file_path, g.thumbnail_path
                    FROM generation_outputs go
                    JOIN generations g ON go.generation_id = g.id
                """).fetchall()
                
                missing_outputs = []
                missing_thumbnails = []
                
                for row in rows:
                    if row['file_path'] and not os.path.exists(row['file_path']):
                        missing_outputs.append(row['id'])
                    
                    if row['thumbnail_path'] and not os.path.exists(row['thumbnail_path']):
                        missing_thumbnails.append(row['generation_id'])
                
                # Remove records with missing files
                for output_id in missing_outputs:
                    conn.execute("DELETE FROM generation_outputs WHERE id = ?", (output_id,))
                    stats["removed_records"] += 1
                
                # Clear missing thumbnail paths
                for generation_id in missing_thumbnails:
                    conn.execute("""
                        UPDATE generations 
                        SET thumbnail_path = NULL 
                        WHERE id = ?
                    """, (generation_id,))
                
                # Remove generations with no outputs
                conn.execute("""
                    DELETE FROM generations 
                    WHERE id NOT IN (
                        SELECT DISTINCT generation_id 
                        FROM generation_outputs
                    )
                """)
                
                # Find orphaned files in output directory
                output_path = Path(output_dir)
                if output_path.exists():
                    db_files = set()
                    
                    # Get all file paths from database
                    file_rows = conn.execute("""
                        SELECT file_path FROM generation_outputs WHERE file_path IS NOT NULL
                        UNION
                        SELECT thumbnail_path FROM generations WHERE thumbnail_path IS NOT NULL
                    """).fetchall()
                    
                    for row in file_rows:
                        if row[0]:  # file_path or thumbnail_path
                            db_files.add(Path(row[0]))
                    
                    # Find files not in database
                    for file_path in output_path.rglob("*"):
                        if file_path.is_file() and file_path not in db_files:
                            try:
                                file_path.unlink()
                                stats["removed_files"] += 1
                            except Exception as e:
                                logger.warning(f"Could not remove orphaned file {file_path}: {e}")
                
                conn.commit()
                
        except Exception as e:
            logger.error(f"Error syncing with filesystem: {e}")
        
        logger.info(f"Filesystem sync complete: {stats}")
        return stats

    def cache_model_schema(self, model_string: str, schema_data: Dict[str, Any]) -> bool:
        """Cache model schema data"""
        try:
            with self._get_connection() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO model_schemas 
                    (model_string, schema_data, last_updated)
                    VALUES (?, ?, ?)
                """, (model_string, json.dumps(schema_data), datetime.now()))
                conn.commit()
                
                logger.debug(f"Cached schema for model {model_string}")
                return True
                
        except Exception as e:
            logger.error(f"Error caching schema for {model_string}: {e}")
            return False

    def get_cached_schema(self, model_string: str) -> Optional[Dict[str, Any]]:
        """Get cached model schema"""
        try:
            with self._get_connection() as conn:
                row = conn.execute("""
                    SELECT schema_data, last_updated 
                    FROM model_schemas 
                    WHERE model_string = ?
                """, (model_string,)).fetchone()
                
                if row:
                    return json.loads(row['schema_data'])
                return None
                
        except Exception as e:
            logger.error(f"Error getting cached schema for {model_string}: {e}")
            return None

    def get_total_generations(self) -> int:
        """Get total number of generations"""
        try:
            with self._get_connection() as conn:
                row = conn.execute("SELECT COUNT(*) as total FROM generations").fetchone()
                return row['total']
        except Exception as e:
            logger.error(f"Error getting total generations: {e}")
            return 0

    def get_database_stats(self) -> Dict[str, Any]:
        """Get database statistics"""
        try:
            with self._get_connection() as conn:
                stats = {}
                
                # Total generations
                stats['total_generations'] = conn.execute("SELECT COUNT(*) as count FROM generations").fetchone()['count']
                
                # Total outputs
                stats['total_outputs'] = conn.execute("SELECT COUNT(*) as count FROM generation_outputs").fetchone()['count']
                
                # Favorites count
                stats['favorites'] = conn.execute("SELECT COUNT(*) as count FROM generations WHERE favorite = 1").fetchone()['count']
                
                # Database size
                stats['db_size_bytes'] = os.path.getsize(self.db_path)
                
                # Most recent generation
                recent_row = conn.execute("SELECT created_at FROM generations ORDER BY created_at DESC LIMIT 1").fetchone()
                if recent_row:
                    stats['most_recent'] = recent_row['created_at']
                
                return stats
                
        except Exception as e:
            logger.error(f"Error getting database stats: {e}")
            return {}
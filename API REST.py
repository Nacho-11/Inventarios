# API REST.py
from flask import Flask, jsonify, request
import sqlite3
from datetime import datetime, timedelta
from flask_cors import CORS  # type: ignore # Para permitir CORS

app = Flask(__name__)
CORS(app)  # Permite solicitudes desde cualquier origen (útil durante desarrollo)

DATABASE = 'inventario_licores.db'

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/api/productos', methods=['GET'])
def get_productos():
    local_id = request.args.get('local_id')
    conn = get_db()
    cursor = conn.cursor()
    
    if local_id:
        cursor.execute("""
            SELECT p.*, 
                   COALESCE((
                       SELECT SUM(CASE WHEN tipo = 'entrada' THEN cantidad_ml ELSE -cantidad_ml END) 
                       FROM movimientos WHERE producto_id = p.id
                   ), 0) as total_ml
            FROM productos p
            WHERE p.local_id = ? AND p.activo = 1
            ORDER BY p.nombre
        """, (local_id,))
    else:
        cursor.execute("""
            SELECT p.*, 
                   COALESCE((
                       SELECT SUM(CASE WHEN tipo = 'entrada' THEN cantidad_ml ELSE -cantidad_ml END) 
                       FROM movimientos WHERE producto_id = p.id
                   ), 0) as total_ml
            FROM productos p
            WHERE p.activo = 1
            ORDER BY p.nombre
        """)
    
    productos = cursor.fetchall()
    conn.close()
    return jsonify([dict(producto) for producto in productos])

@app.route('/api/movimientos', methods=['GET', 'POST'])
def movimientos():
    conn = get_db()
    cursor = conn.cursor()
    
    if request.method == 'GET':
        producto_id = request.args.get('producto_id')
        limit = request.args.get('limit', 50)
        
        query = """
        SELECT m.*, p.nombre as producto_nombre, u.nombre as usuario_nombre
        FROM movimientos m
        JOIN productos p ON m.producto_id = p.id
        JOIN usuarios u ON m.user_id = u.id
        """
        params = []
        
        if producto_id:
            query += " WHERE m.producto_id = ?"
            params.append(producto_id)
        
        query += " ORDER BY m.fecha DESC LIMIT ?"
        params.append(limit)
        
        cursor.execute(query, params)
        movimientos = cursor.fetchall()
        conn.close()
        return jsonify([dict(mov) for mov in movimientos])
    
    elif request.method == 'POST':
        data = request.json
        cursor.execute("""
        INSERT INTO movimientos (producto_id, user_id, tipo, cantidad_ml, peso_bruto, notas)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (
            data['producto_id'], 
            data['user_id'], 
            data['tipo'], 
            data['cantidad_ml'], 
            data.get('peso_bruto'), 
            data.get('notas', '')
        ))
        conn.commit()
        conn.close()
        return jsonify({"status": "success"}), 201

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("""
    SELECT id, nombre, rol, local_id FROM usuarios 
    WHERE username = ? AND password = ? AND activo = 1
    """, (data['username'], data['password']))
    
    usuario = cursor.fetchone()
    conn.close()
    
    if usuario:
        return jsonify(dict(usuario))
    else:
        return jsonify({"error": "Credenciales inválidas"}), 401

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
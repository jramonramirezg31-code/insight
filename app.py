import os
from flask import Flask, render_template, request, redirect, url_for, session, flash
import psycopg2

app = Flask(__name__)

# Clave secreta leída desde las variables de Render o una por defecto
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'L@ser2310')

# ==========================================
# CONEXIÓN INTEGRAL A POSTGRESQL (LA NUBE)
# ==========================================
def obtener_conexion():
    # Intenta leer la variable secreta de Render (Session Pooler puerto 6543)
    url_conexion = os.environ.get('DATABASE_URL')
    
    # Si por alguna razón estás en local o no detecta la variable, usa la de respaldo corregida
    if not url_conexion:
        url_conexion = 'postgresql://postgres:L@ser.2310@db.fzpaqqixgadcgawhuptl.supabase.co:6543/postgres'
    
    # Regla de oro para drivers de Postgres en Flask
    if url_conexion.startswith("postgres://"):
        url_conexion = url_conexion.replace("postgres://", "postgresql://", 1)
        
    return psycopg2.connect(url_conexion)

# ==========================================
# RUTAS DE AUTENTICACIÓN
# ==========================================
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method != 'POST':
        return render_template('login.html')
        
    usuario = request.form['username']
    contra = request.form['password']
    try:
        conn = obtener_conexion()
        cursor = conn.cursor()
        cursor.execute("SELECT contra FROM usuarios WHERE usuario = %s", (usuario,))
        row = cursor.fetchone()
        conn.close()
        
        if row is not None and row[0] == contra:
            session['usuario'] = usuario
            return redirect(url_for('inicio'))
            
        flash('Usuario o contraseña incorrectos', 'danger')
    except Exception as e:
        print(f"Error crítico en Login: {e}")
        flash('Error de comunicación con el servidor', 'danger')
        
    return redirect(url_for('login'))

@app.route('/logout')
def logout():
    session.pop('usuario', None)
    return redirect(url_for('login'))

# ==========================================
# 1. PÁGINA DE INICIO (CAPTURA DE PEDIDOS)
# ==========================================
@app.route('/')
def inicio():
    if 'usuario' not in session:
        return redirect(url_for('login'))
    return render_template('pedidos.html')

@app.route('/agregar', methods=['POST'])
def agregar_pedido():
    if 'usuario' not in session:
        return redirect(url_for('login'))

    cliente = request.form['cliente']
    descripcion = request.form['descripcion']
    fecha = request.form['fecha']
    total = request.form['total']
    
    try:
        conn = obtener_conexion()
        cursor = conn.cursor()
        # %s universal para PostgreSQL
        query = "INSERT INTO pedidos2 (cliente, descripcion, fecha_entrega, total, estatus) VALUES (%s, %s, %s, %s, 'Pendiente')"
        cursor.execute(query, (cliente, descripcion, fecha, total))
        conn.commit()
        conn.close()
        flash('Pedido registrado con éxito', 'success')
    except Exception as e:
        print(f"Error al insertar en PostgreSQL: {e}")
        flash('Error al guardar el pedido', 'danger')
        
    return redirect(url_for('inicio')) 

# ==========================================
# 2. SECCIÓN DEL DASHBOARD (CALENDARIO)
# ==========================================
@app.route('/dashboard')
def dashboard_inicio():
    if 'usuario' not in session:
        return redirect(url_for('login'))

    totales = {'total': 0, 'pendiente': 0, 'diseno': 0, 'corte': 0, 'listo': 0}
    eventos_calendario = []

    try:
        conn = obtener_conexion()
        cursor = conn.cursor()
        cursor.execute("SELECT estatus, cliente, fecha_entrega FROM pedidos2")
        rows = cursor.fetchall()
        
        for row in rows:
            estado_limpio = row[0].strip().lower() if row[0] else 'pendiente'
            cliente = row[1]
            fecha_objeto = row[2] 
            
            totales['total'] += 1
            if 'diseño' in estado_limpio or 'diseno' in estado_limpio:
                totales['diseno'] += 1
                color = '#0dcaf0'
            elif 'corte' in estado_limpio or 'cortando' in estado_limpio:
                totales['corte'] += 1
                color = '#ffc107'
            elif 'listo' in estado_limpio or 'completo' in estado_limpio:
                totales['listo'] += 1
                color = '#198754'
            else:
                totales['pendiente'] += 1
                color = '#6c757d'

            if fecha_objeto:
                # Python convierte la fecha nativa a texto de forma segura
                fecha_texto = fecha_objeto.strftime('%Y-%m-%d')
                eventos_calendario.append({
                    'title': f"📦 {cliente}",
                    'start': fecha_texto,
                    'color': color
                })
                
        conn.close()
    except Exception as e:
        print(f"Error en Dashboard con Calendario: {e}")
    
    return render_template('dashboard.html', kpis=totales, eventos=eventos_calendario)

# ==========================================
# 3. PANTALLA DE ADMINISTRACIÓN (CRUD)
# ==========================================
@app.route('/admin')
def admin_pedidos():
    if 'usuario' not in session:
        return redirect(url_for('login'))

    pedidos_formateados = []
    try:
        conn = obtener_conexion()
        cursor = conn.cursor()
        cursor.execute("SELECT id_pedido, cliente, descripcion, fecha_entrega, total, estatus FROM pedidos2 ORDER BY id_pedido DESC")
        rows = cursor.fetchall()
        
        for row in rows:
            # Mandamos la fecha formateada desde Python para evitar conflictos con Jinja o SQL
            fecha_str = row[3].strftime('%d-%m-%Y') if row[3] else ''
            pedidos_formateados.append({
                "id": row[0], "cliente": row[1], "descripcion": row[2], 
                "fecha": fecha_str, "total": row[4], "estatus": row[5]
            })
        conn.close()
    except Exception as e:
        print(f"Error al leer PostgreSQL para Admin: {e}")
    
    return render_template('admin_pedidos.html', lista_pedidos=pedidos_formateados)

@app.route('/editar_estado/<int:id_pedido>/<string:nuevo_estado>')
def editar_estado(id_pedido, nuevo_estado):
    if 'usuario' not in session:
        return redirect(url_for('login'))

    try:
        conn = obtener_conexion()
        cursor = conn.cursor()
        query = "UPDATE pedidos2 SET estatus = %s WHERE id_pedido = %s"
        cursor.execute(query, (nuevo_estado, id_pedido))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error al actualizar estado: {e}")
        
    return redirect(url_for('admin_pedidos'))

@app.route('/eliminar/<int:id_pedido>')
def eliminar_pedido(id_pedido):
    if 'usuario' not in session:
        return redirect(url_for('login'))

    try:
        conn = obtener_conexion()
        cursor = conn.cursor()
        # Cambiado '?' por '%s' que es el estándar de Postgres
        query = "DELETE FROM pedidos2 WHERE id_pedido = %s"
        cursor.execute(query, (id_pedido,))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error al eliminar pedido: {e}")
        
    return redirect(url_for('admin_pedidos'))

if __name__ == '__main__':
    app.run(debug=True)

from flask import Flask, render_template, request, redirect, url_for, session, flash
import os
import psycopg2  # <-- Cambiado pyodbc por psycopg2 para PostgreSQL

app = Flask(__name__)

# La clave secreta la leerá de internet de forma segura, si no existe usa una por defecto
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'clave_local_secreta_insight')

# ==========================================
# CONEXIÓN ADAPTADA A POSTGRESQL (LA NUBE)
# ==========================================
def obtener_conexion():
    # Render y los servidores en la nube te dan una "Connection String" o URL completa.
    # El código la buscará automáticamente en internet, y si estás en tu PC local,
    # puedes pegar tu URL de Supabase/Neon temporalmente aquí.
    url_conexion = os.environ.get('DATABASE_URL', 'postgresql://postgres:[L@ser.2310]@db.fzpaqqixgadcgawhuptl.supabase.co:5432/postgres')
    return psycopg2.connect(url_conexion)
# ==========================================
# RUTAS DE AUTENTICACIÓN (LOGIN Y LOGOUT)
# ==========================================

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        usuario_ingresado = request.form['usuario']
        password_ingresado = request.form['password']
        
        usuario_encontrado = None
        try:
            conn = obtener_conexion()
            cursor = conn.cursor()
            query = "SELECT usuario FROM usuarios WHERE usuario = %s AND contra = %s"
            cursor.execute(query, (usuario_ingresado, password_ingresado))
            row = cursor.fetchone()
            if row:
                usuario_encontrado = row[0]
            conn.close()
        except Exception as e:
            print(f"Error al verificar usuario en SQL Server: {e}")
            flash("Error de conexión con la base de datos.")
            return redirect(url_for('login'))
        
        if usuario_encontrado:
            session['usuario'] = usuario_encontrado
            return redirect(url_for('index')) # Te manda a la página de inicio (Pedidos) al loguearte
        else:
            flash('Usuario o contraseña incorrectos.')
            return redirect(url_for('login'))
            
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('usuario', None)
    return redirect(url_for('login'))


# ==========================================
# 1. PÁGINA DE INICIO CONSTANTE: FORMULARIO Y LISTA DE PEDIDOS
# ==========================================
@app.route('/')
def index():
    if 'usuario' not in session:
        return redirect(url_for('login'))

    pedidos_formateados = []
    try:
        conn = obtener_conexion()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id_pedido, cliente, descripcion, CONVERT(VARCHAR, fecha_entrega, 23), total, estatus 
            FROM pedidos2
        """)
        rows = cursor.fetchall()
        for row in rows:
            pedidos_formateados.append({
                "id": row[0], "cliente": row[1], "descripcion": row[2], 
                "fecha": row[3], "total": row[4], "estatus": row[5]
            })
        conn.close()
    except Exception as e:
        print(f"Error al leer pedidos en Inicio: {e}")
        
    return render_template('pedidos.html', lista_pedidos=pedidos_formateados)


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
        query = "INSERT INTO pedidos2 (cliente, descripcion, fecha_entrega, total, estatus) VALUES (%s, %s, %s, %s, 'Pendiente')"
        cursor.execute(query, (cliente, descripcion, fecha, total))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error al insertar en SQL Server: {e}")
        
    return redirect(url_for('index')) # Al agregar, te deja en la misma página de inicio


# ==========================================
# 2. APARTADO INDEPENDIENTE: SECCIÓN DEL DASHBOARD
# ==========================================
@app.route('/dashboard')
def dashboard_inicio():
    if 'usuario' not in session:
        return redirect(url_for('login'))

    totales = {'total': 0, 'pendiente': 0, 'diseno': 0, 'corte': 0, 'listo': 0}
    eventos_calendario = [] # <-- Nueva lista para el calendario

    try:
        conn = obtener_conexion()
        cursor = conn.cursor()
        
        # Traemos también el cliente y la fecha para el calendario
        cursor.execute("""
            SELECT estatus, cliente, CONVERT(VARCHAR, fecha_entrega, 23) 
            FROM pedidos2
        """)
        rows = cursor.fetchall()
        
        for row in rows:
            estado_limpio = row[0].strip().lower() if row[0] else 'pendiente'
            cliente = row[1]
            fecha = row[2]
            
            # 1. Lógica de los contadores (KPIs)
            totales['total'] += 1
            if 'diseño' in estado_limpio or 'diseno' in estado_limpio:
                totales['diseno'] += 1
                color = '#0dcaf0' # Azul info
            elif 'corte' in estado_limpio or 'cortando' in estado_limpio:
                totales['corte'] += 1
                color = '#ffc107' # Amarillo warning
            elif 'listo' in estado_limpio or 'completo' in estado_limpio:
                totales['listo'] += 1
                color = '#198754' # Verde success
            else:
                totales['pendiente'] += 1
                color = '#6c757d' # Gris secondary

            # 2. Estructuramos el pedido como un evento para FullCalendar
            if fecha:
                eventos_calendario.append({
                    'title': f"📦 {cliente}",
                    'start': fecha,
                    'color': color # El calendario pintará el evento del color de su estatus
                })
                
        conn.close()
    except Exception as e:
        print(f"Error en Dashboard con Calendario: {e}")
    
    # Mandamos los KPIs y la lista de eventos al HTML
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
        cursor.execute("""
            SELECT id_pedido, cliente, descripcion, CONVERT(VARCHAR, fecha_entrega, 23), total, estatus
            FROM pedidos2
        """)
        rows = cursor.fetchall()
        
        for row in rows:
            pedidos_formateados.append({
                "id": row[0], "cliente": row[1], "descripcion": row[2], 
                "fecha": row[3], "total": row[4], "estatus": row[5]
            })
        conn.close()
    except Exception as e:
        print(f"Error al leer SQL Server para Admin: {e}")
    
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
        query = "DELETE FROM pedidos2 WHERE id_pedido = ?"
        cursor.execute(query, [id_pedido])
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error al eliminar pedido: {e}")
        
    return redirect(url_for('admin_pedidos'))


if __name__ == '__main__':
    app.run(debug=True)
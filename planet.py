#!/usr/bin/python3

######################################
#
#   Copyright (C) 2019 P.L. Lucas
#
#
# LICENSE: BSD
# You may use this file under the terms of the BSD license as follows:
#
# "Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are
# met:
#   * Redistributions of source code must retain the above copyright
#     notice, this list of conditions and the following disclaimer.
#   * Redistributions in binary form must reproduce the above copyright
#     notice, this list of conditions and the following disclaimer in
#     the documentation and/or other materials provided with the
#     distribution.
#   * Neither the name of developers or companies in the above copyright, Digia Plc and its 
#     Subsidiary(-ies) nor the names of its contributors may be used to 
#     endorse or promote products derived from this software without 
#     specific prior written permission.
#
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE."
#
#
######################################/


import feedparser
import sqlite3
import calendar
import time
import threading
import sys
import webbrowser

def procesar_blog(sql_conn, blog):
    d = feedparser.parse(blog)
    sql_cursor = sql_conn.cursor()
    for post in d.entries:
        fecha = None
        if 'updated_parsed' in post:
            fecha = post.updated_parsed
        elif 'published_parsed' in post:
            fecha = post.published_parsed
        sql_cursor.execute("""
            insert or replace into feeds (blog, titulo, enlace, fecha)
            values(?, ?, ?, ?);
        """, (d.feed.title, post.title, post.link, calendar.timegm(fecha)) )
    sql_conn.commit()
    pass

def limpiar_base_datos(sql_conn):
    # Se eliminan todas las entradas con una antigüedad de 1 año
    sql_cursor = sql_conn.cursor()
    fecha_hace_un_agno = int(time.time()) - 365*24*60*60
    sql_cursor.execute("delete from feeds where fecha<? ", (fecha_hace_un_agno,))
    sql_conn.commit()

def cabecera_html(fout, sql_cursor, numero_pagina):
    final_entradas = False
    
    fin = open("cabecera.html", 'r')
    for line in fin:
        if line == '<!-- Contenidos -->\n':
            i = 0
            for row in sql_cursor:
                fecha = time.gmtime(int(row[3]))
                fout.write("""
                <tr>
                    <td>{0}</td><td>{3}</td>
                    <td><a href='{2}' target='blank'>{1}</a></td>
                </tr>
                """.format(row[0], row[1], row[2], "{0}-{1}-{2}".format(fecha[0], fecha[1], fecha[2])))
                i += 1
                if i == 1000:                                
                    final_entradas = True
                    break                                
        
        fout.write(line)
        
    archivo_anterior = 'pagina-{0}.html'.format(numero_pagina - 1)
    archivo_siguiente = 'pagina-{0}.html'.format(numero_pagina + 1)
    
    if numero_pagina > 1:
        fout.write("<p><a href='{0}'>Anterior</a></p>".format(archivo_anterior))
        
    if final_entradas:
        fout.write("<p><a href='{0}'>Siguiente</a></p>".format(archivo_siguiente))    
           
    fin.close()
    
    return final_entradas

def generar_html(sql_conn):
    n = 0
    pagina = 1
    sql_cursor = sql_conn.cursor()
    archivo_actual = 'pagina-{0}.html'.format(pagina)
    archivo_anterior = None
    fout = open('salida/' + archivo_actual, 'w')
    sql_cursor.execute("select blog, titulo, enlace, fecha from feeds order by fecha desc")
    
    while cabecera_html(fout, sql_cursor, pagina):        
        pagina += 1
        fout.close()
        fout = open('salida/pagina-{0}.html'.format(pagina), 'w')        
        
    fout.close()

# Esta clase sirve para gestionar los hilos
class Hilos(threading.Thread):
    def __init__(self, blog, semaforo):
        threading.Thread.__init__(self)
        self.sql_conn = None 
        self.blog = blog
        self.semaforo = semaforo

    def run(self):
        semaforo.acquire()
        print('Procesando... {0}'.format(self.blog))
        self.sql_conn = sqlite3.connect('feeds.db')
        procesar_blog(self.sql_conn, self.blog)
        self.sql_conn.commit()
        self.sql_conn.close()
        semaforo.release()


# Se abre/crea la base de datos de feeds
# TODO: Hacer una segunda tabla con el nombre del blog
sql_conn = sqlite3.connect('feeds.db')
sql_cursor = sql_conn.cursor()
sql_cursor.execute("""
    create table if not exists feeds
    (
        blog text, titulo text, enlace text, fecha int,
        primary key (enlace)
    );
    """)
sql_conn.commit()


# Se busca el listado de blogs en "blogs_feeds.txt" y se procesan
fin = open("blogs_feeds.txt")
semaforo = threading.Semaphore(10)  # Se permiten 10 a la vez
hilos = []
for blog in fin:
    hilo = Hilos(blog, semaforo)
    hilos.append(hilo)
    hilo.start()
fin.close()
for hilo in hilos:
    hilo.join()

# Se borran las entradas antiguas para que la base de datos no se haga enorme
limpiar_base_datos(sql_conn)

# Se generan los html en el directorio salida
generar_html(sql_conn)

# Se cierra la base de datos
sql_conn.close()

# Se comprueban los argumentos de la línea de comandos
navegadorOk = False
for arg in sys.argv:
    if '--no-browser' == arg:
        navegadorOk = False

if navegadorOk:
    # Se abre en el navegador la primera página de la salida:
    webbrowser.open('salida/pagina-1.html')


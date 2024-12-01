# HookedDocs Database

Este repositorio contiene los scripts necesarios para implementar y gestionar la base de datos del proyecto **HookedDocs**. La base de datos se ejecuta en un contenedor Docker con **Oracle Database Express Edition 21c**.

## Requisitos

- **Base de datos**: Oracle Database Express Edition 21c (implementada en Docker).
- **Docker**: Asegúrate de tener Docker instalado y configurado para correr el contenedor de la base de datos.
- **SQL Developer o equivalente**: Para gestionar la base de datos y ejecutar los scripts.

## Scripts Incluidos

### 1. **HookedDocs_tables.sql**

- **Descripción**: Este script crea las tablas necesarias para la base de datos del proyecto **HookedDocs**.
- **Contenido principal**:
  - Definición de las tablas base para manejar facturas, productos, usuarios, y otros datos relacionados con la gestión del sistema.
  - Configuración de restricciones, claves primarias y relaciones entre tablas.
- **Uso**:
  Ejecutar este script en la base de datos Oracle 21c antes de trabajar con los procedimientos almacenados.

### 2. **HookedDocs_PKG.sql**

- **Descripción**: Este script implementa un paquete PL/SQL llamado `HookedDocs_PKG`, que contiene procedimientos y funciones necesarios para operar sobre las tablas creadas.
- **Contenido principal**:
  - Procedimientos para la inserción, actualización, eliminación y consulta de datos.
  - Funciones específicas para validar y gestionar operaciones relacionadas con el sistema HookedDocs.
  - Auditoría de cambios y validación de datos ingresados.
- **Uso**:
  Ejecutar este script después de haber creado las tablas con `HookedDocs_tables.sql`.

## Pasos para la Implementación

1. **Iniciar el contenedor Docker con Oracle Database 21c**:
   - Usa la imagen oficial de Oracle para levantar un contenedor con los puertos necesarios configurados.
   - Asegúrate de que el puerto `1521` esté abierto para conexiones locales y remotas.

   - mostrar contenedores 
        docker ps -a

    - lanzar o parar contenedores
        docker start <nombre contenedor o ID>
        docker stop <nombre contenedor o ID>

    - Permitir el acceso al puerto 1521 en el firewall.

## Conexión sqlDeveloper

    Host: consultar IP remota para conectividad externa
    Puerto: 1521
    Service Name: XEPDB1
    Usuario: HookedDeveloper
    Contraseña: HookedDeveloperDuoc2024


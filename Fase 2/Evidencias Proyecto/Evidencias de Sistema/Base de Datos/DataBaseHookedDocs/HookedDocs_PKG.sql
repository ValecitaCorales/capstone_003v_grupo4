--------------------------------------------------------
--  DDL for Procedure SET_TIMEZONE_CHILE
--------------------------------------------------------
set define off;

  CREATE OR REPLACE EDITIONABLE PROCEDURE "HOOKEDDEVELOPER"."SET_TIMEZONE_CHILE" AS
BEGIN
  -- Configura la zona horaria para Santiago, Chile
  EXECUTE IMMEDIATE 'ALTER SESSION SET TIME_ZONE = ''America/Santiago''';
END;

/
--------------------------------------------------------
--  DDL for Package PKG_ISSUED
--------------------------------------------------------

  CREATE OR REPLACE EDITIONABLE PACKAGE "HOOKEDDEVELOPER"."PKG_ISSUED" AS 

    PROCEDURE MAIN;
  
    PROCEDURE SP_JSON_TO_FLAT_TABLE;
    
    PROCEDURE AUDIT_INVOICE_ISSUED;

END PKG_ISSUED;

/
--------------------------------------------------------
--  DDL for Package PKG_LOG_DEPURATION
--------------------------------------------------------

  CREATE OR REPLACE EDITIONABLE PACKAGE "HOOKEDDEVELOPER"."PKG_LOG_DEPURATION" AS 

    FUNCTION FN_LOG_DEPURATION(p_invoice_number NUMBER) RETURN NUMBER;
    
    FUNCTION FN_REGISTER_AUDIT_LOG(p_process number) return varchar2;

END PKG_LOG_DEPURATION;

/
--------------------------------------------------------
--  DDL for Package PKG_RECEIVED
--------------------------------------------------------

  CREATE OR REPLACE EDITIONABLE PACKAGE "HOOKEDDEVELOPER"."PKG_RECEIVED" AS 

    PROCEDURE MAIN;

    PROCEDURE SP_JSON_TO_FLAT_TABLE;

    PROCEDURE AUDIT_INVOICE_RECEIVED;

END pkg_received;

/
--------------------------------------------------------
--  DDL for Package Body PKG_ISSUED
--------------------------------------------------------

  CREATE OR REPLACE EDITIONABLE PACKAGE BODY "HOOKEDDEVELOPER"."PKG_ISSUED" AS 

--variables de paquete
v_step      VARCHAR2(100);
v_pkg       CONSTANT VARCHAR(20) := 'PKG_ISSUED';
v_sp        VARCHAR2(30);
v_sqlcode   VARCHAR2(200);
v_sqlerrm   VARCHAR2(200);

    PROCEDURE MAIN IS
    
    --VARIABLES

    BEGIN
        
        --PKG ORQUESTADOR PARA PROCEDO DE FACTURACION EMITIDA
        
        v_sp := UPPER('MAIN');
        -- LIMPIEZA LOG
        DELETE FROM hd_log_debug WHERE UPPER(procedure_executed) = v_sp;
        COMMIT;
        
        -- SETEAMOS LA ZONA HORARIA
        set_timezone_chile;
        
        INSERT INTO hd_log_debug (desc_log, procedure_executed)VALUES ('Ejecutando SP_JSON_TO_FLAT_TABLE', v_sp);
        pkg_issued.sp_json_to_flat_table;
       
        INSERT INTO hd_log_debug (desc_log, procedure_executed)VALUES ('Ejecutando AUDIT_INVOICE_ISSUED', v_sp);
        pkg_issued.audit_invoice_issued;


    EXCEPTION WHEN OTHERS THEN

        --rollback;
        v_sqlcode := SQLCODE;
        v_sqlerrm := sqlerrm;
        --agregar tabla de log interna estado de ejecucion database
        INSERT INTO hd_log_debug (desc_log, procedure_executed)
        VALUES ('ERROR: en '||v_sp||' *** '||v_sqlcode||' *** '||v_sqlerrm, v_sp);

    END MAIN;

/**************************************TRASPASO DE TABLAS DE PASO A FINAL*****************************************/
    PROCEDURE sp_json_to_flat_table IS

    --variables
    v_count NUMBER;

    BEGIN
        v_sp := UPPER('sp_json_to_flat_table');
        
        -- LIMPIEZA LOG
        DELETE FROM hd_log_debug WHERE UPPER(procedure_executed) = v_sp;
        COMMIT;
        --dbms_output.put_line('1');
        
        INSERT INTO hd_log_debug (desc_log, procedure_executed)VALUES ('Inicio', v_sp);

        ---------
        v_step:= 'insert into FLAT_INVOICES_RECEIVED';
        ---------
        INSERT INTO flat_invoices_issued (
            create_date
            ,pay_method
            ,subtotal
            ,tax
            ,total
            ,issuer_name
            ,issuer_rut
            ,issuer_economic_activity
            ,issuer_address
            ,issuer_email
            ,issuer_phone
            ,invoice_number
            ,invoice_type
            ,issue_date
            ,buyer_name
            ,buyer_rut
            ,buyer_economic_activity
            ,buyer_address
            ,buyer_commune)
        SELECT
            ii.create_date,
            jt.pay_method,
            jt.subtotal,
            jt.tax,
            jt.total,
            jt.issuer_name,
            jt.issuer_rut,
            jt.issuer_economic_activity,
            jt.issuer_address,
            jt.issuer_email,
            jt.issuer_phone,
            TO_NUMBER(jt.invoice_number) AS invoice_number,
            jt.invoice_type,
            TO_DATE(jt.issue_date, 'DDMMYYYY') AS issue_date,
            jt.buyer_name,
            jt.buyer_rut,
            jt.buyer_economic_activity,
            jt.buyer_address,
            jt.buyer_commune      
        FROM invoices_issued ii
        CROSS APPLY
            JSON_TABLE(
                ii.invoice_data, '$'
                COLUMNS (
                    pay_method      VARCHAR2(50)  PATH '$.pay_method',
                    subtotal        NUMBER        PATH '$.subtotal',
                    tax             NUMBER        PATH '$.tax',
                    total           NUMBER        PATH '$.total',
                    --issuer
                    issuer_name     VARCHAR2(100) PATH '$.issuer.name',
                    issuer_rut      VARCHAR2(20)  PATH '$.issuer.rut',
                    issuer_economic_activity    VARCHAR2(200)PATH '$.issuer.economic_activity',
                    issuer_address              VARCHAR2(200)PATH '$.issuer.address',
                    issuer_email                VARCHAR2(200)PATH '$.issuer.email',
                    issuer_phone                VARCHAR2(20) PATH '$.issuer.phone',
                    invoice_number              VARCHAR2(20) PATH '$.issuer.invoice_number',
                    invoice_type                VARCHAR2(200)PATH '$.issuer.invoice_type',
                    issue_date                  VARCHAR2(8)  PATH '$.issuer.issue_date',
                    --buyer
                    buyer_name                  VARCHAR2(100)PATH '$.buyer.name',
                    buyer_rut                   VARCHAR2(20) PATH '$.buyer.rut',
                    buyer_economic_activity     VARCHAR2(200)PATH '$.buyer.economic_activity',
                    buyer_address               VARCHAR2(200)PATH '$.buyer.address',
                    buyer_commune               VARCHAR2(200)PATH '$.buyer.commune'
                )
            ) jt
        WHERE TO_NUMBER(jt.invoice_number) NOT IN (SELECT invoice_number FROM flat_invoices_issued);
        

        v_count := SQL%rowcount; 

        INSERT INTO hd_log_debug (desc_log, procedure_executed)VALUES ('Fin, filas procesadas en flat_invoices_issued = '||v_count,  v_sp);
        
        COMMIT;

        
        ---------
        v_step:= 'insert into flat_invoices_issued_items';
        ---------
        INSERT INTO flat_invoices_issued_items (
            invoice_number_fk
            ,item_description
            ,item_quantity
            ,item_unit_price
            ,item_total_price
            ,create_date
            )
        SELECT
            jt.invoice_number,
            jt.item_description,
            jt.item_quantity,
            jt.item_unit_price,
            jt.item_total_price,
            ii.create_date
        FROM invoices_issued ii
        CROSS APPLY
            JSON_TABLE(
                ii.invoice_data, '$'
                COLUMNS (
                    invoice_number  VARCHAR2(20)  PATH '$.issuer.invoice_number',
                    NESTED PATH '$.items[*]' COLUMNS (
                        item_description VARCHAR2(100) PATH '$.description',
                        item_quantity    VARCHAR2(20)  PATH '$.quantity',
                        item_unit_price  NUMBER        PATH '$.unit_price',
                        item_total_price NUMBER        PATH '$.total_price'
                    )
                )
            ) jt
        --WHERE to_char(ii.create_date,'DDMMRRRR') = to_char(current_timestamp,'DDMMRRRR')
        WHERE jt.invoice_number NOT IN (SELECT invoice_number_fk FROM flat_invoices_issued_items);
            
        v_count := SQL%rowcount; 
        
        -- limpieza tabla de paso
        EXECUTE IMMEDIATE 'truncate table INVOICES_ISSUED';
            
        INSERT INTO hd_log_debug (desc_log, procedure_executed)VALUES ('Fin, filas procesadas en flat_invoices_issued_items= '||v_count,  v_sp);
            
        COMMIT;
            
    
    EXCEPTION WHEN OTHERS THEN

        ROLLBACK;
 
        v_sqlcode := SQLCODE;
        v_sqlerrm := sqlerrm;
        INSERT INTO hd_log_debug (desc_log, procedure_executed)
        VALUES ('ERROR al procesar '||v_step||' *** '||v_sqlcode||' *** '||v_sqlerrm, v_sp);

    END sp_json_to_flat_table;

/**************************************PROCESO DE VALIDACION DE DATOS EN TABLA FINAL*****************************************/
    PROCEDURE audit_invoice_issued IS
    
        --variables
        v_total                 NUMBER;
        v_validation_message    VARCHAR2(255);
        v_process               VARCHAR2(100):='Facturas emitidas';
        v_issuer_name           VARCHAR2(20):='El Senuelo';
    
        CURSOR c_invoices_issued IS
            SELECT 
                ID,
                subtotal, 
                tax, 
                total,
                pay_method, 
                issuer_rut, 
                invoice_number, 
                invoice_type, 
                buyer_name, 
                buyer_rut,
                create_date
            FROM flat_invoices_issued;
            --WHERE to_char(create_date,'DDMMRRRR') = to_char(current_timestamp,'DDMMRRRR');
        
        /*CURSOR c_invoices_issued_items(p_fk NUMBER) IS
            SELECT 
                SUM(item_total_price) AS item_total_price
            FROM flat_invoices_issued_items t1
            WHERE t1.invoice_number_fk = p_fk
            --AND to_char(create_date,'DDMMRRRR') = to_char(current_timestamp,'DDMMRRRR');
            ;*/
    
    BEGIN
        v_sp := UPPER('audit_invoice_issued');
        
        -- LIMPIEZA LOG
        DELETE FROM hd_log_debug WHERE UPPER(procedure_executed) = v_sp;
        
        DELETE FROM invoice_audit_log WHERE PROCESS = v_process;
        COMMIT;
    
        INSERT INTO hd_log_debug (desc_log, procedure_executed)VALUES ('Inicio auditoria contabilidad', v_sp);
        
        FOR I IN c_invoices_issued LOOP
    
            /*******************************AUDITORIA CONTABILIDAD***************************************/
        --  SUBTOTAL, TAX, TOTAL
    
             -- Validar que el campo subtotal o neto no sea nulo o cero
            IF I.subtotal IS NULL OR I.subtotal = 0 THEN
                v_validation_message := 'ERROR - Subtotal es nulo o cero';
                
                INSERT INTO invoice_audit_log(invoice_id, issue_date, validation_message, PROCESS, issuer_name)
                VALUES (CASE I.invoice_number WHEN NULL THEN I.ID ELSE I.invoice_number END, I.create_date, v_validation_message, v_process, v_issuer_name);
                
            END IF;
    
    
            /*FOR J IN c_invoices_issued_items(I.invoice_number) LOOP
            
                -- Validar que el campo ITEM_TOTAL_PRICE no sea nulo o 0 y no sea diferente al neto
                IF J.item_total_price IS NULL OR J.item_total_price = 0 THEN
                    v_validation_message := 'ERROR - suma totales precios unitarios es nulo o cero';
                    
                    INSERT INTO invoice_audit_log(invoice_id, issue_date, validation_message, process, ISSUER_NAME)
                    VALUES (CASE I.invoice_number WHEN NULL THEN I.ID ELSE I.invoice_number END, I.create_date, v_validation_message, v_process, v_issuer_name);
                    
                    IF J.item_total_price <> I.subtotal THEN
                        v_validation_message := 'ERROR - la suma de los items por factura es diferente al valor neto';
                        
                        INSERT INTO invoice_audit_log(invoice_id, issue_date, validation_message, process, ISSUER_NAME)
                        VALUES (CASE I.invoice_number WHEN NULL THEN I.ID ELSE I.invoice_number END, I.create_date, v_validation_message, v_process, v_issuer_name);
                    
                    END IF;
                END IF;
            
            END LOOP;*/
    
            -- Validar que el campo tax (impuesto / IVA) no sea nulo o cero
            IF I.tax IS NULL OR I.tax = 0 THEN
                v_validation_message := 'ERROR - Impuesto es nulo o cero';
                INSERT INTO invoice_audit_log(invoice_id, issue_date, validation_message, PROCESS, issuer_name)
                VALUES (CASE I.invoice_number WHEN NULL THEN I.ID ELSE I.invoice_number END, I.create_date, v_validation_message, v_process, v_issuer_name);
                
            END IF;
    
            -- Validar que el campo total no sea nulo o cero
            IF I.total IS NULL OR I.total = 0 THEN
                v_validation_message := 'ERROR - Total es nulo o cero';
                
                INSERT INTO invoice_audit_log(invoice_id, issue_date, validation_message, PROCESS, issuer_name)
                VALUES (CASE I.invoice_number WHEN NULL THEN I.ID ELSE I.invoice_number END, I.create_date, v_validation_message, v_process, v_issuer_name);
                
            END IF;
    
            -- El total tiene que ser la suma del neto + iva
            v_total := 0;
            v_total := (I.subtotal + I.tax);

            IF v_total != I.total THEN
                v_validation_message := 'ERROR - Total es diferente de la suma de valores neto+iva';
                
                INSERT INTO invoice_audit_log(invoice_id, issue_date, validation_message, PROCESS, issuer_name)
                VALUES (CASE I.invoice_number WHEN NULL THEN I.ID ELSE I.invoice_number END, I.create_date, v_validation_message, v_process, v_issuer_name);
                
            END IF;
    
            /*******************************AUDITORIA INTEGRIDAD DE DATOS***************************************/
            --PAY_METHOD, ISSUER_RUT, INVOICE_NUMBER, INVOICE_TYPE, BUYER_NAME, BUYER_RUT
    
            -- Validar que PAY_METHOD  no sea nulo
            IF I.pay_method IS NULL THEN
                v_validation_message := 'WARNING - Metodo de pago nulo';
                
                INSERT INTO invoice_audit_log(invoice_id, issue_date, validation_message, PROCESS, issuer_name)
                VALUES (CASE I.invoice_number WHEN NULL THEN I.ID ELSE I.invoice_number END, I.create_date, v_validation_message, v_process, v_issuer_name);
            END IF;
            
            -- Validar que ISSUER_RUT no sea null
            IF I.issuer_rut IS NULL THEN
                v_validation_message := 'ERROR - El rut del emisor es nulo';
                
                INSERT INTO invoice_audit_log(invoice_id, issue_date, validation_message, PROCESS, issuer_name)
                VALUES (CASE I.invoice_number WHEN NULL THEN I.ID ELSE I.invoice_number END, I.create_date, v_validation_message, v_process, v_issuer_name);
                
            END IF;
    
            -- Validar que INVOICE_NUMBER del emisor no sea null
            IF I.invoice_number IS NULL THEN
                v_validation_message := 'ERROR - el numero de factura es nula';
                
                INSERT INTO invoice_audit_log(invoice_id, issue_date, validation_message, PROCESS, issuer_name)
                VALUES (CASE I.invoice_number WHEN NULL THEN I.ID ELSE I.invoice_number END, I.create_date, v_validation_message, v_process, v_issuer_name);
                
            END IF;
            
            -- Validar que INVOICE_TYPE no sea null
            IF I.invoice_type IS NULL THEN
                v_validation_message := 'WARNING - Tipo de documento es nulo';
                
                INSERT INTO invoice_audit_log(invoice_id, issue_date, validation_message, PROCESS, issuer_name)
                VALUES (CASE I.invoice_number WHEN NULL THEN I.ID ELSE I.invoice_number END, I.create_date, v_validation_message, v_process, v_issuer_name);
                
            END IF;
            
            -- Validar que BUYER_NAME no sea null
            IF I.buyer_name IS NULL THEN
                v_validation_message := 'WARNING - El nombre del comprador es nulo';
                
                INSERT INTO invoice_audit_log(invoice_id, issue_date, validation_message, PROCESS, issuer_name)
                VALUES (CASE I.invoice_number WHEN NULL THEN I.ID ELSE I.invoice_number END, I.create_date, v_validation_message, v_process, v_issuer_name);
                
            END IF;
            
            -- Validar que BUYER_RUT no sea null
            IF I.buyer_rut IS NULL THEN
                v_validation_message := 'WARNING - El rut del comprador es nulo';
                
                INSERT INTO invoice_audit_log(invoice_id, issue_date, validation_message, PROCESS, issuer_name)
                VALUES (CASE I.invoice_number WHEN NULL THEN I.ID ELSE I.invoice_number END, I.create_date, v_validation_message, v_process, v_issuer_name);
                
            END IF;
            
            COMMIT;
            
        END LOOP;
        
        INSERT INTO hd_log_debug (desc_log, procedure_executed)VALUES ('Fin', v_sp);    COMMIT;
    
        
    EXCEPTION WHEN OTHERS THEN
    
        ROLLBACK;
        
        v_sqlcode := SQLCODE;
        v_sqlerrm := sqlerrm;
        
        INSERT INTO hd_log_debug (desc_log, procedure_executed)
        VALUES ('ERROR: '||v_sqlcode||' '||v_sqlerrm, v_sp);
    
    END audit_invoice_issued;


END pkg_issued;

/
--------------------------------------------------------
--  DDL for Package Body PKG_LOG_DEPURATION
--------------------------------------------------------

  CREATE OR REPLACE EDITIONABLE PACKAGE BODY "HOOKEDDEVELOPER"."PKG_LOG_DEPURATION" AS 

v_pkg       CONSTANT VARCHAR(20) := 'PKG_LOG_DEPURATION';
v_sp        VARCHAR2(30);
v_sqlcode   VARCHAR2(200);
v_sqlerrm   VARCHAR2(200);

    FUNCTION FN_LOG_DEPURATION(p_invoice_number NUMBER) RETURN NUMBER IS
    
    --variables
    v_flag number := 0;

    BEGIN 

        v_sp := UPPER('FN_LOG_DEPURATION');
        -- LIMPIEZA LOG
        DELETE FROM hd_log_debug WHERE UPPER(procedure_executed) = v_sp;
        COMMIT;

        set_timezone_chile;
        
        select 1 
            into v_flag
        from invoice_audit_log where INVOICE_ID = p_invoice_number;

        if v_flag = 1 then
            INSERT INTO hd_log_debug (desc_log, procedure_executed)
            VALUES ('INICIO', v_sp);
    
                
            --DELETE
            DELETE FROM invoice_audit_log WHERE INVOICE_ID = p_invoice_number;
            
            INSERT INTO hd_log_debug (desc_log, procedure_executed)
            VALUES ('DELETE, EJECUTADO NUMERO: '||p_invoice_number, v_sp);
    
    
            INSERT INTO hd_log_debug (desc_log, procedure_executed)
            VALUES ('FIN', v_sp);
        
        
            
        else 
            INSERT INTO hd_log_debug (desc_log, procedure_executed)
            VALUES ('REGISTRO ELIMINADO '||p_invoice_number||' NO POSEE VALIDACION PENDIENTE', v_sp);
        end if;
        
        COMMIT;
        
        return 0;

    EXCEPTION WHEN OTHERS THEN

        RETURN 1;
        rollback;
        v_sqlcode := sqlcode;
        v_sqlerrm := sqlerrm;
        --agregar tabla de log interna estado de ejecucion database
        insert into HD_LOG_DEBUG (desc_log, procedure_executed)
        values ('ERROR: '||v_sqlcode||' '||v_sqlerrm, v_pkg);
        COMMIT;

    END FN_LOG_DEPURATION;

/**************************************FUNCION DE AUDITORIA DE DATOS PROCESADOS*****************************************/

    FUNCTION FN_REGISTER_AUDIT_LOG(p_process number) return varchar2 IS
    
    --variables
    v_total     number := 0;
    v_errors    number := 0;
    v_table     varchar2(100);

    BEGIN 
    
        v_sp := UPPER('FN_REGISTER_AUDIT_LOG');
        -- LIMPIEZA LOG
        DELETE FROM hd_log_debug WHERE UPPER(procedure_executed) = v_sp;
        COMMIT;

        set_timezone_chile;
        
        INSERT INTO hd_log_debug (desc_log, procedure_executed)
            VALUES ('INICIO', v_sp);
        
        
        v_table := case
                        when p_process = 1 then 'FLAT_INVOICES_RECEIVED'
                        when p_process = 2 then 'FLAT_INVOICES_ISSUED'
                        when p_process = 3 then 'PHYSICAL_TICKETS'
                        when p_process = 4 then 'ELECTRONIC_TICKETS'
                    end;
    

       
        EXECUTE IMMEDIATE 'SELECT COUNT(*) FROM ' || v_table || ' WHERE TO_DATE(create_date, ''DD/MM/YYYY'') = TO_DATE(to_CHAR(CURRENT_TIMESTAMP, ''DD/MM/YYYY''), ''DD/MM/YYYY'')' INTO v_total;
        
        
        SELECT COUNT(*) 
            INTO v_errors
        FROM invoice_audit_log
        WHERE ISSUE_DATE = TO_DATE(to_CHAR(CURRENT_TIMESTAMP, 'DD/MM/YYYY'), 'DD/MM/YYYY');

        
    if v_total > 0 and v_errors >= 0 then
        return 'Se insertaron '||v_total||' registros, ALERTAS detectadas: '||v_errors;
    else
        return 'No hay registros';
    end if;
 
    commit;
    
    EXCEPTION WHEN OTHERS THEN

        RETURN 'ERROR '||sqlcode||' '||sqlerrm;

        v_sqlcode := sqlcode;
        v_sqlerrm := sqlerrm;
        --agregar tabla de log interna estado de ejecucion database
        insert into HD_LOG_DEBUG (desc_log, procedure_executed)
        values ('ERROR: '||v_sqlcode||' '||v_sqlerrm, v_pkg);
    
    END FN_REGISTER_AUDIT_LOG;

END PKG_LOG_DEPURATION;

/
--------------------------------------------------------
--  DDL for Package Body PKG_RECEIVED
--------------------------------------------------------

  CREATE OR REPLACE EDITIONABLE PACKAGE BODY "HOOKEDDEVELOPER"."PKG_RECEIVED" AS 

--variables de paquete
v_step      VARCHAR2(100);
v_pkg       CONSTANT VARCHAR(20) := 'PKG_RECEIVED';
v_sp        VARCHAR2(30);
v_sqlcode   VARCHAR2(200);
v_sqlerrm   VARCHAR2(200);

    PROCEDURE MAIN IS
    
    --VARIABLES
    v_sqlcode varchar2(200);
    v_sqlerrm varchar2(200);

    BEGIN
        --PKG ORQUESTADOR PARA PROCEDO DE FACTURACION recibida
        
        v_sp := UPPER('MAIN');
        -- LIMPIEZA LOG
        DELETE FROM hd_log_debug WHERE UPPER(procedure_executed) = v_sp;
        COMMIT;
        
        -- SETEAMOS LA ZONA HORARIA
        set_timezone_chile;
        
        INSERT INTO hd_log_debug (desc_log, procedure_executed)VALUES ('Ejecutando SP_JSON_TO_FLAT_TABLE', v_sp);
        pkg_received.sp_json_to_flat_table;

        INSERT INTO hd_log_debug (desc_log, procedure_executed)VALUES ('Ejecutando AUDIT_INVOICE_ISSUED', v_sp);
        pkg_received.audit_invoice_received;

    EXCEPTION WHEN OTHERS THEN

        rollback;
        v_sqlcode := sqlcode;
        v_sqlerrm := sqlerrm;
        --agregar tabla de log interna estado de ejecucion database
        insert into HD_LOG_DEBUG (desc_log, procedure_executed)
        values ('ERROR: '||v_sqlcode||' '||v_sqlerrm, v_pkg);

    END MAIN;

/**************************************TRASPASO DE TABLAS DE PASO A FINAL*****************************************/
    PROCEDURE sp_json_to_flat_table IS

    --variables
    v_count NUMBER;

    BEGIN
        v_sp := UPPER('sp_json_to_flat_table');
        
        -- LIMPIEZA LOG
        DELETE FROM hd_log_debug WHERE UPPER(procedure_executed) = v_sp;
        COMMIT;
        --dbms_output.put_line('1');
        
        INSERT INTO hd_log_debug (desc_log, procedure_executed)VALUES ('Inicio', v_sp);

        ---------
        v_step:= 'insert into FLAT_INVOICES_RECEIVED';
        ---------
        INSERT INTO FLAT_INVOICES_RECEIVED (
            CREATE_DATE
            ,PAY_METHOD
            ,SUBTOTAL
            ,TAX
            ,TOTAL
            ,INVOICE_NUMBER
            ,ISSUE_DATE
            ,ISSUER_NAME
            ,ISSUER_RUT
            ,ISSUER_ADDRESS
            ,ISSUER_EMAIL
            ,ISSUER_PHONE)
        SELECT
            ii.create_date,
            jt.pay_method,
            jt.subtotal,
            jt.tax,
            jt.total,
            to_number(jt.invoice_number) as invoice_number,
            TO_DATE(jt.issue_date, 'DDMMYYYY') AS issue_date,
            jt.issuer_name,
            jt.issuer_rut,
            jt.issuer_address,
            jt.issuer_email,
            jt.issuer_phone         
        FROM invoices_received ii
        CROSS APPLY
            JSON_TABLE(
                ii.invoice_data, '$'
                COLUMNS (
                    pay_method      VARCHAR2(50)  PATH '$.pay_method',
                    subtotal        NUMBER        PATH '$.subtotal',
                    tax             NUMBER        PATH '$.tax',
                    total           NUMBER        PATH '$.total',
                    invoice_number  VARCHAR2(20)  PATH '$.invoice_number',
                    issue_date      VARCHAR2(8)   PATH '$.issue_date',
                    --issuer
                    issuer_name     VARCHAR2(100) PATH '$.issuer.name',
                    issuer_rut      VARCHAR2(20)  PATH '$.issuer.rut',
                    issuer_address  VARCHAR2(200) PATH '$.issuer.address',
                    issuer_email  VARCHAR2(200) PATH '$.issuer.email',
                    issuer_phone  VARCHAR2(20) PATH '$.issuer.phone'
                )
            ) jt
        where jt.invoice_number not in (SELECT invoice_number FROM FLAT_INVOICES_RECEIVED);
        

        v_count := SQL%rowcount; 

        INSERT INTO hd_log_debug (desc_log, procedure_executed)VALUES ('Fin, filas procesadas en FLAT_INVOICES_RECEIVED = '||v_count,  v_sp);
        
        COMMIT;
            
        ---------
        v_step:= 'insert into FLAT_INVOICES_RECEIVED_ITEMS';
        ---------
        INSERT INTO FLAT_INVOICES_RECEIVED_ITEMS(
        INVOICE_NUMBER_FK
        ,ITEM_DESCRIPTION
        ,ITEM_QUANTITY
        ,ITEM_SKU
        ,ITEM_UNIT_PRICE
        ,ITEM_DISCOUNT
        ,ITEM_TOTAL_PRICE
        ,CREATE_DATE)
     SELECT
            to_number(jt.invoice_number) as invoice_number,
            jt.item_description,
            jt.item_quantity,
            jt.item_sku,
            jt.item_unit_price,
            jt.item_discount,
            jt.item_total_price,
            ii.create_date
        FROM invoices_received ii
        CROSS APPLY
            JSON_TABLE(
                ii.invoice_data, '$'
                COLUMNS (
                    invoice_number  VARCHAR2(20)  PATH '$.invoice_number',
                    NESTED PATH '$.items[*]' COLUMNS (
                        item_description VARCHAR2(100) PATH '$.description',
                        item_quantity    VARCHAR2(20)  PATH '$.quantity',
                        item_sku    VARCHAR2(20)  PATH '$.sku',
                        item_unit_price  NUMBER        PATH '$.unit_price',
                        item_discount  NUMBER        PATH '$.discount',
                        item_total_price NUMBER        PATH '$.subtotal'
                    )
                )
            ) jt
        where jt.invoice_number not in (SELECT invoice_number_fk FROM FLAT_INVOICES_RECEIVED_ITEMS);
        
        v_count := SQL%rowcount; 
        
        -- limpieza tabla de paso
        execute immediate 'truncate table INVOICES_RECEIVED';
            
        INSERT INTO hd_log_debug (desc_log, procedure_executed)VALUES ('Fin, filas procesadas en FLAT_INVOICES_RECEIVED_ITEMS = '||v_count,  v_sp);
            
        COMMIT;

    EXCEPTION WHEN OTHERS THEN
        ROLLBACK;

        
        v_sqlcode := SQLCODE;
        v_sqlerrm := sqlerrm;
        INSERT INTO hd_log_debug (desc_log, procedure_executed)
        VALUES ('ERROR: '||v_sqlcode||' '||v_sqlerrm, 'audit_invoice');

    END sp_json_to_flat_table;

/**************************************PROCESO DE VALIDACION DE DATOS EN TABLA FINAL*****************************************/
    PROCEDURE audit_invoice_received IS

        --variables
        v_invoice_data JSON;
        v_pay_method VARCHAR2(100);
        v_invoice_number number;
        v_subtotal NUMBER;
        v_tax NUMBER;
        v_total NUMBER;
        v_issue_date VARCHAR2(8);
        v_issue_name    varchar2(200);
        v_validation_message VARCHAR2(255);
        v_sqlcode varchar2(200);
        v_sqlerrm varchar2(200);
        v_process varchar2(100):='Facturas recibidas';

    CURSOR c_invoices_received IS
        SELECT
            t1.create_date,
            t1.pay_method,
            t1.subtotal,
            t1.tax,
            t1.total,
            t1.invoice_number,
            t1.issue_date,
            t1.issuer_name,
            t1.issuer_rut,
            t1.issuer_address,
            t1.issuer_email,
            t1.issuer_phone,
            t1.id
        FROM
            flat_invoices_received t1;
            --WHERE to_char(create_date,'DDMMRRRR') = to_char(current_timestamp,'DDMMRRRR');
        
        CURSOR c_invoices_received_items(p_fk number) IS
            SELECT 
                ITEM_DESCRIPTION
                ,ITEM_QUANTITY
                ,ITEM_SKU
                ,ITEM_UNIT_PRICE
                ,ITEM_DISCOUNT
                ,ITEM_TOTAL_PRICE
                ,INVOICE_NUMBER_FK
            FROM flat_invoices_received_items t1
            WHERE t1.invoice_number_fk = p_fk
            --AND to_char(create_date,'DDMMRRRR') = to_char(current_timestamp,'DDMMRRRR');
            ;

    BEGIN
        v_sp := UPPER('audit_invoice_issued');
        
        -- LIMPIEZA LOG
        DELETE FROM hd_log_debug WHERE UPPER(procedure_executed) = v_sp;
    
        DELETE from invoice_audit_log WHERE PROCESS = v_process;
        COMMIT;
    
        INSERT INTO hd_log_debug (desc_log, procedure_executed)VALUES ('Inicio auditoria contabilidad', v_sp);
        
        FOR I IN c_invoices_received LOOP
    
            /*******************************AUDITORIA CONTABILIDAD***************************************/
        --  SUBTOTAL, TAX, TOTAL
    
             -- Validar que el campo subtotal o neto no sea nulo o cero
            IF I.subtotal IS NULL OR I.subtotal = 0 THEN
                v_validation_message := 'ERROR - Subtotal es nulo o cero';
                
                INSERT INTO invoice_audit_log(invoice_id, issue_date, validation_message, PROCESS, issuer_name)
                VALUES (CASE I.invoice_number WHEN NULL THEN I.ID ELSE I.invoice_number END, I.create_date, v_validation_message, v_process, i.issuer_name);
                
            END IF;
    
            /*
            -- Validar que el campo ITEM_TOTAL_PRICE no sea nulo o 0 y no sea diferente al neto
            IF i.item_total_price IS NULL OR i.item_total_price = 0 THEN
                v_validation_message := 'ERROR - suma totales precios unitarios es nulo o cero';
                
                INSERT INTO invoice_audit_log(invoice_id, issue_date, validation_message, PROCESS, issuer_name)
                VALUES (CASE I.invoice_number WHEN NULL THEN I.ID ELSE I.invoice_number END, I.create_date, v_validation_message, v_process, i.issuer_name);
                
            END IF;
            
            IF i.item_total_price <> i.subtotal THEN
                v_validation_message := 'ERROR - la suma de los items por factura es diferente al valor neto';
                    
                INSERT INTO invoice_audit_log(invoice_id, issue_date, validation_message, PROCESS, issuer_name)
                VALUES (CASE I.invoice_number WHEN NULL THEN I.ID ELSE I.invoice_number END, I.create_date, v_validation_message, v_process, i.issuer_name);
            
            END IF;*/
            
            -- Validar que el campo tax (impuesto / IVA) no sea nulo o cero
            IF I.tax IS NULL OR I.tax = 0 THEN
                v_validation_message := 'ERROR - Impuesto es nulo o cero';
                INSERT INTO invoice_audit_log(invoice_id, issue_date, validation_message, PROCESS, issuer_name)
                VALUES (CASE I.invoice_number WHEN NULL THEN I.ID ELSE I.invoice_number END, I.create_date, v_validation_message, v_process, i.issuer_name);
                
            END IF;
    
            -- Validar que el campo total no sea nulo o cero
            IF I.total IS NULL OR I.total = 0 THEN
                v_validation_message := 'ERROR - Total es nulo o cero';
                
                INSERT INTO invoice_audit_log(invoice_id, issue_date, validation_message, PROCESS, issuer_name)
                VALUES (CASE I.invoice_number WHEN NULL THEN I.ID ELSE I.invoice_number END, I.create_date, v_validation_message, v_process, i.issuer_name);
                
            END IF;
    
            -- El total tiene que ser la suma del neto + iva
            v_total := 0;
            v_total := (I.subtotal + I.tax);

            IF v_total != I.total THEN
                v_validation_message := 'ERROR - Total es diferente de la suma de valores neto+iva';
                
                INSERT INTO invoice_audit_log(invoice_id, issue_date, validation_message, PROCESS, issuer_name)
                VALUES (CASE I.invoice_number WHEN NULL THEN I.ID ELSE I.invoice_number END, I.create_date, v_validation_message, v_process, i.issuer_name);
                
            END IF;
    
            /*******************************AUDITORIA INTEGRIDAD DE DATOS***************************************/
            --PAY_METHOD, ISSUER_RUT, INVOICE_NUMBER, INVOICE_TYPE, BUYER_NAME, BUYER_RUT
    
            -- Validar que PAY_METHOD  no sea nulo
            IF I.pay_method IS NULL THEN
                v_validation_message := 'WARNING - Metodo de pago nulo';
                
                INSERT INTO invoice_audit_log(invoice_id, issue_date, validation_message, PROCESS, issuer_name)
                VALUES (CASE I.invoice_number WHEN NULL THEN I.ID ELSE I.invoice_number END, I.create_date, v_validation_message, v_process, i.issuer_name);
            END IF;
            
            -- Validar que issuer_name no sea null
            IF I.issuer_name IS NULL THEN
                v_validation_message := 'WARNING - Nombre del remitente es nulo';
                
                INSERT INTO invoice_audit_log(invoice_id, issue_date, validation_message, PROCESS, issuer_name)
                VALUES (CASE I.invoice_number WHEN NULL THEN I.ID ELSE I.invoice_number END, I.create_date, v_validation_message, v_process, i.issuer_name);
                
            END IF;
            
            -- Validar que ISSUER_RUT no sea null
            IF I.issuer_rut IS NULL THEN
                v_validation_message := 'ERROR - El rut del emisor es nulo';
                
                INSERT INTO invoice_audit_log(invoice_id, issue_date, validation_message, PROCESS, issuer_name)
                VALUES (CASE I.invoice_number WHEN NULL THEN I.ID ELSE I.invoice_number END, I.create_date, v_validation_message, v_process, i.issuer_name);
                
            END IF;
    
            -- Validar que INVOICE_NUMBER del emisor no sea null
            IF I.invoice_number IS NULL THEN
                v_validation_message := 'ERROR - el numero de factura es nula';
                
                INSERT INTO invoice_audit_log(invoice_id, issue_date, validation_message, PROCESS, issuer_name)
                VALUES (CASE I.invoice_number WHEN NULL THEN I.ID ELSE I.invoice_number END, I.create_date, v_validation_message, v_process, i.issuer_name);
                
            END IF;
            
            for j in c_invoices_received_items(i.invoice_number) loop
            
                -- Validar que ITEM_DESCRIPTION no sea null
                IF j.ITEM_DESCRIPTION IS NULL THEN
                    v_validation_message := 'WARNING - La descripcion del producto esta vacia';
                    
                    INSERT INTO invoice_audit_log(invoice_id, issue_date, validation_message, PROCESS, issuer_name)
                    VALUES (CASE I.invoice_number WHEN NULL THEN I.ID ELSE I.invoice_number END, I.create_date, v_validation_message, v_process, i.issuer_name);
                    
                END IF;
                
                -- Validar que ITEM_UNIT_PRICE no sea null
                IF j.ITEM_UNIT_PRICE IS NULL THEN
                    v_validation_message := 'ERROR - El valor unitario del producto esta vacio';
                    
                    INSERT INTO invoice_audit_log(invoice_id, issue_date, validation_message, PROCESS, issuer_name)
                    VALUES (CASE I.invoice_number WHEN NULL THEN I.ID ELSE I.invoice_number END, I.create_date, v_validation_message, v_process, i.issuer_name);
                    
                END IF;
                
                -- Validar que ITEM_TOTAL_PRICE no sea null
                IF j.ITEM_TOTAL_PRICE IS NULL THEN
                    v_validation_message := 'ERROR - El subtotal de la suma de valores unitarios del producto esta vacio';
                    
                    INSERT INTO invoice_audit_log(invoice_id, issue_date, validation_message, PROCESS, issuer_name)
                    VALUES (CASE I.invoice_number WHEN NULL THEN I.ID ELSE I.invoice_number END, I.create_date, v_validation_message, v_process, i.issuer_name);
                    
                END IF;
            
            end loop;
            
            COMMIT;
            
        END LOOP;
        
        INSERT INTO hd_log_debug (desc_log, procedure_executed)VALUES ('Fin', v_sp);    COMMIT;
    
        
    exception when others then
        rollback;
        v_sqlcode := sqlcode;
        v_sqlerrm := sqlerrm;
        --agregar tabla de log interna estado de ejecucion database
        insert into HD_LOG_DEBUG (desc_log, procedure_executed)
        values ('ERROR: '||v_sqlcode||' '||v_sqlerrm||' '||v_invoice_number, 'audit_invoice');

    END audit_invoice_received;

END pkg_received;

/

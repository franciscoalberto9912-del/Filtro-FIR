`timescale 1ns/1ps

module tb_fir;

    //========================================================
    // Señales del DUT
    //========================================================

    logic clk;
    logic rst;

    logic [7:0] in;
    logic [7:0] y;

    logic smp;

    logic [2:0]  dir_h;
    logic        store_h;
    logic [15:0] coe;
    logic        start;


    //========================================================
    // DUT
    //========================================================

    fir dut (
        .clk     (clk),
        .rst     (rst),
        .in      (in),
        .y       (y),
        .smp     (smp),
        .dir_h   (dir_h),
        .store_h (store_h),
        .coe     (coe),
        .start    (start)
    );


    //========================================================
    // CLOCK
    // 27 MHz
    // Periodo = 37.037 ns
    //========================================================

    initial begin
        clk = 1'b0;
        forever #18.5185 clk = ~clk;
    end


    //========================================================
    // MEMORIA DE ENTRADA
    //========================================================

    logic [7:0] muestras [0:13199];

    integer num_muestras;
    integer i;


    initial begin

        $readmemb("python/entrada.txt", muestras);

        $display("Archivo entrada.txt cargado.");

    end


    //========================================================
    // ARCHIVO DE SALIDA
    //========================================================

    integer archivo_salida;

    initial begin
        archivo_salida = $fopen("python/salida.txt", "w");

        if (archivo_salida == 0) begin
            $display("ERROR: no se pudo abrir salida.txt");
            $finish;
        end
    end


    //========================================================
    // CARGAR COEFICIENTE
    //========================================================

    task cargar_coeficiente;

        input [2:0] direccion;
        input signed [15:0] coeficiente;

        begin

            @(negedge clk);

            dir_h   = direccion;
            coe     = coeficiente;
            store_h = 1'b1;

            @(negedge clk);

            store_h = 1'b0;

        end

    endtask


    //========================================================
    // TEST PRINCIPAL
    //========================================================

    initial begin

        // Valores iniciales
        rst        = 1'b0;
        in         = 8'd0;
        dir_h      = 3'd0;
        coe        = 16'd0;
        store_h    = 1'b0;
        start      = 1'b0;

        //====================================================
        // RESET
        //====================================================

        repeat (5)
            @(posedge clk);

        rst = 1'b1;


        //====================================================
        // CARGAR COEFICIENTES
        //====================================================

        // EJEMPLO:
        //
// Cambia estos valores por tus coeficientes Q2.14 los coeficientes a continucacion son para 5khz
	cargar_coeficiente(3'd0, -16'sd360);
        cargar_coeficiente(3'd1, -16'sd1484);
        cargar_coeficiente(3'd2, -16'sd1388);
        cargar_coeficiente(3'd3, 16'sd3232);
        cargar_coeficiente(3'd4, 16'sd3232);
        cargar_coeficiente(3'd5, -16'sd1388);
        cargar_coeficiente(3'd6, -16'sd1484);
        cargar_coeficiente(3'd7, -16'sd360);











        //====================================================
        // START
        //====================================================

        @(negedge clk);

        start = 1'b1;

        @(negedge clk);

        start = 1'b0;


        //====================================================
        // ENVIAR MUESTRAS
        //====================================================

        num_muestras = 0;

        // Primera muestra
        @(negedge clk);

        in = muestras[num_muestras];

        num_muestras = num_muestras + 1;


        //====================================================
        // BUCLE PRINCIPAL
        //====================================================

        while (num_muestras < 13200) begin

            // Esperamos el pulso de sample
            @(posedge clk);

            if (smp) begin

                // La salida corresponde al procesamiento
                // de muestras anteriores debido al pipeline.
                //
                // Guardamos y al mismo tiempo preparamos
                // la siguiente muestra.

                $fwrite(
                    archivo_salida,
                    "%08b\n",
                    y
                );

                @(negedge clk);

                in = muestras[num_muestras];

                num_muestras = num_muestras + 1;

            end

        end


        //====================================================
        // CERRAR
        //====================================================

        $fclose(archivo_salida);

        $display("----------------------------------");
        $display("Simulacion terminada");
        $display("Muestras procesadas: %0d", num_muestras);
        $display("Salida guardada en salida.txt");
        $display("----------------------------------");

        #100;

        $finish;

    end


    //========================================================
    // MONITOR
    //========================================================

    always @(posedge clk) begin

        if (smp) begin

            $display(
                "t=%0t ns | muestra=%0d | entrada=%0d | salida=%0d",
                $time,
                num_muestras,
                in,
                y
            );

        end

    end

endmodule

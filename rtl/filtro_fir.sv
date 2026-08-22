module fir (
    input  logic        clk,
    input  logic        rst,

    input  logic [7:0]  in,
    output logic [7:0]  y,

    output logic        smp,

    // Carga de coeficientes
    input  logic [2:0]  dir_h,
    input  logic        store_h,
    input  logic [15:0] coe,

    // Inicio del filtro
    input  logic        start
);

    // Estados

    typedef enum logic {
        IDLE,
        RUN
    } state_t;

    state_t state;

    // Muestras

    logic [7:0] n [0:7];

    // Coeficientes Q2.14
    logic signed [15:0] h [0:7];

    // Indica qué coeficientes ya fueron cargados
    logic [7:0] h_valid;

    // Productos
    logic signed [23:0] p [0:7];
    // Árbol de sumadores
    logic signed [24:0] s0, s1, s2, s3;
    logic signed [25:0] s4, s5;

    logic signed [26:0] acumulador;
    logic signed [26:0] resultado;


    // Generador de frecuencia de muestreo


    logic [10:0] counter;
    logic       sample;

    assign smp = sample;


    // Máquina de estados


    always_ff @(posedge clk or negedge rst) begin

        if (!rst) begin
            state   <= IDLE;
            h_valid <= '0;
        end

        else begin

            case (state)


                IDLE: begin

                    // Cargar coeficiente
                    if (store_h) begin
                        h[dir_h] <= coe;
                        h_valid[dir_h] <= 1'b1;
                    end

                    // Iniciar filtro solamente cuando
                    // los 8 coeficientes estén cargados
                    if (start && (&h_valid)) begin
                        state <= RUN;
                    end

                end


              

                RUN: begin
                    // El filtro funciona mediante sample
                    state <= RUN;
                end

            endcase
        end
    end


    always_ff @(posedge clk or negedge rst) begin

        if (!rst) begin
            counter <= '0;
            sample  <= 1'b0;
        end

        else if (state != RUN) begin
            counter <= '0;
            sample  <= 1'b0;
        end

        else begin

            counter <= counter + 1'b1;

            if (counter == 8'h7f)
                sample <= 1'b1;
            else
                sample <= 1'b0;

        end
    end


    always_ff @(posedge clk or negedge rst) begin

        if (!rst) begin
    for (int i = 0; i < 8; i++)
        n[i] <= '0;
end

        else if (state == RUN && sample) begin

            for (int i = 7; i > 0; i = i - 1)
                n[i] <= n[i-1];

            n[0] <= in;

        end

    end


    always_ff @(posedge clk or negedge rst) begin

       if (!rst) begin
    for (int i = 0; i < 8; i++)
        p[i] <= '0;
end
        else if (state == RUN && sample) begin

            for (int i = 0; i < 8; i = i + 1) begin

                p[i] <=
                    $signed({1'b0, n[i]}) * h[i];

            end

        end

    end


    always_ff @(posedge clk or negedge rst) begin

        if (!rst) begin

            s0 <= '0;
            s1 <= '0;
            s2 <= '0;
            s3 <= '0;

            s4 <= '0;
            s5 <= '0;

            acumulador <= '0;

        end

        else if (state == RUN && sample) begin

            // Nivel 1
            s0 <= p[0] + p[1];
            s1 <= p[2] + p[3];
            s2 <= p[4] + p[5];
            s3 <= p[6] + p[7];

            // Nivel 2
            s4 <= s0 + s1;
            s5 <= s2 + s3;
            // Nivel 3
            acumulador <= s4 + s5;

        end

    end

    // Q2.14 -> entero
    // Saturación a 8 bits

    always @* begin

        resultado = acumulador >>> 14;

        if (resultado < 0)
            y = 8'd0;

        else if (resultado > 255)
            y = 8'd255;

        else
            y = resultado[7:0];

    end

endmodule

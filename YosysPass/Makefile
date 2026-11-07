YOSYS_CONFIG ?= yosys-config

PASSES :=  stuttering show_regs_mems MiterStutteringPass RegMemInitPass Stalling
OBJS := $(patsubst %, bin/%.so,${PASSES})

.PHONY: all clean
all: ${OBJS}

clean:
	rm -f ${OBJS}

bin/%.so: %.cc
	${YOSYS_CONFIG} --build $@ $^ 
	rm -f $(@:.so=.d)

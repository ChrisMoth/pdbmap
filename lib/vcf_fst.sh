 #!/bin/bash -e
 lib/vcftools/bin/vcftools \
--vcf - \
--weir-fst-pop <(grep AMR /dors/capra_lab/data/1kg/vcf/integrated_call_samples_v3.20130502.ALL.panel) \
--weir-fst-pop <(grep EAS /dors/capra_lab/data/1kg/vcf/integrated_call_samples_v3.20130502.ALL.panel) \
--stdout | lib/vcftools/bin/vcftools --vcf - \
--weir-fst-pop <(grep AMR /dors/capra_lab/data/1kg/vcf/integrated_call_samples_v3.20130502.ALL.panel) \
--weir-fst-pop <(grep SAS /dors/capra_lab/data/1kg/vcf/integrated_call_samples_v3.20130502.ALL.panel) \
--stdout | lib/vcftools/bin/vcftools --vcf - \
--weir-fst-pop <(grep AMR /dors/capra_lab/data/1kg/vcf/integrated_call_samples_v3.20130502.ALL.panel) \
--weir-fst-pop <(grep EUR /dors/capra_lab/data/1kg/vcf/integrated_call_samples_v3.20130502.ALL.panel) \
--stdout | lib/vcftools/bin/vcftools --vcf - \
--weir-fst-pop <(grep AMR /dors/capra_lab/data/1kg/vcf/integrated_call_samples_v3.20130502.ALL.panel) \
--weir-fst-pop <(grep AFR /dors/capra_lab/data/1kg/vcf/integrated_call_samples_v3.20130502.ALL.panel) \
--stdout | lib/vcftools/bin/vcftools --vcf - \
--weir-fst-pop <(grep EAS /dors/capra_lab/data/1kg/vcf/integrated_call_samples_v3.20130502.ALL.panel) \
--weir-fst-pop <(grep SAS /dors/capra_lab/data/1kg/vcf/integrated_call_samples_v3.20130502.ALL.panel) \
--stdout | lib/vcftools/bin/vcftools --vcf - \
--weir-fst-pop <(grep EAS /dors/capra_lab/data/1kg/vcf/integrated_call_samples_v3.20130502.ALL.panel) \
--weir-fst-pop <(grep EUR /dors/capra_lab/data/1kg/vcf/integrated_call_samples_v3.20130502.ALL.panel) \
--stdout | lib/vcftools/bin/vcftools --vcf - \
--weir-fst-pop <(grep EAS /dors/capra_lab/data/1kg/vcf/integrated_call_samples_v3.20130502.ALL.panel) \
--weir-fst-pop <(grep AFR /dors/capra_lab/data/1kg/vcf/integrated_call_samples_v3.20130502.ALL.panel) \
--stdout | lib/vcftools/bin/vcftools --vcf - \
--weir-fst-pop <(grep SAS /dors/capra_lab/data/1kg/vcf/integrated_call_samples_v3.20130502.ALL.panel) \
--weir-fst-pop <(grep EUR /dors/capra_lab/data/1kg/vcf/integrated_call_samples_v3.20130502.ALL.panel) \
--stdout | lib/vcftools/bin/vcftools --vcf - \
--weir-fst-pop <(grep SAS /dors/capra_lab/data/1kg/vcf/integrated_call_samples_v3.20130502.ALL.panel) \
--weir-fst-pop <(grep AFR /dors/capra_lab/data/1kg/vcf/integrated_call_samples_v3.20130502.ALL.panel) \
--stdout | lib/vcftools/bin/vcftools --vcf - \
--weir-fst-pop <(grep EUR /dors/capra_lab/data/1kg/vcf/integrated_call_samples_v3.20130502.ALL.panel) \
--weir-fst-pop <(grep AFR /dors/capra_lab/data/1kg/vcf/integrated_call_samples_v3.20130502.ALL.panel) \
--stdout | lib/vcftools/bin/vcftools --vcf - \
--weir-fst-pop <(grep AMR /dors/capra_lab/data/1kg/vcf/integrated_call_samples_v3.20130502.ALL.panel) \
--weir-fst-pop <(grep EAS /dors/capra_lab/data/1kg/vcf/integrated_call_samples_v3.20130502.ALL.panel) \
--weir-fst-pop <(grep SAS /dors/capra_lab/data/1kg/vcf/integrated_call_samples_v3.20130502.ALL.panel) \
--weir-fst-pop <(grep EUR /dors/capra_lab/data/1kg/vcf/integrated_call_samples_v3.20130502.ALL.panel) \
--weir-fst-pop <(grep AFR /dors/capra_lab/data/1kg/vcf/integrated_call_samples_v3.20130502.ALL.panel) \
--stdout

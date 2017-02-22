#Purpose of this script is to download imagenet data from Shivypoo's s3 bucket
#Assumes that s3cmd is installed
DATA_DIR="${1%/}"
SCRATCH_DIR="${DATA_DIR}/raw-data/"
mkdir -p "${DATA_DIR}"
mkdir -p "${SCRATCH_DIR}"
WORK_DIR="$0.runfiles/inception/inception"

DOWNLOAD_CMD="s3cmd get --recursive"

#Download scaled validation data
VAL_TAR="s3://imagenet-validation-all-scaled-tar"
VAL_DIR="${SCRATCH_DIR}validation/"
"${DOWNLOAD_CMD}" "${VAL_TAR}" "${VAL_DIR}"

#Download scaled training data
TRAINING_TAR="s3://imagenet-train-all-scaled-tar"
TRAINING_DIR="${SCRATCH_DIR}validation/"
"${DOWNLOAD_CMD}" "${TRAINING_TAR}" "${TRAINING_DIR}"

#Untar each of the files in validation 
#"for f in *.tar; do tar xf $f; done"
#"for f in *.tar; rm $f; done

mv imagenet-train-all-scaled-tar/ raw_data/


import argparse
from pathlib import Path

from src.logger import setup_logger
from src.pipeline import Pipeline


def main():

    parser = argparse.ArgumentParser(
        description=
        "Generate subtitles using Qwen3-ASR"
    )


    parser.add_argument(
        "video",
        help="input video file"
    )


    args = parser.parse_args()


    logger = setup_logger()


    video = Path(args.video)


    if not video.exists():

        logger.error(
            f"File not found: {video}"
        )

        return 1


    pipeline = Pipeline()


    pipeline.run(
        video
    )


    return 0



if __name__ == "__main__":

    exit(
        main()
    )
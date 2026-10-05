# Model selection and primary references

Model cards and official interfaces were checked on 5 October 2026. Weights are
downloaded separately and are not redistributed in this application archive.

| Model / service | Checked information | Application decision |
|---|---|---|
| [amazon/chronos-2](https://huggingface.co/amazon/chronos-2) | Apache-2.0; 120M parameters; CPU/GPU and univariate/multivariate/covariate support; pandas `predict_df` API | Optional CPU adapter; only univariate history is used by this release. Requires own-store benchmarking, not a universal winner claim |
| [amazon/chronos-bolt-tiny](https://huggingface.co/amazon/chronos-bolt-tiny) | Apache-2.0; approximately 9M parameters; direct quantile forecasts; CPU option | Lighter candidate for a later adapter/benchmark. Not currently a selectable app method |
| [BAAI/bge-small-en-v1.5](https://huggingface.co/BAAI/bge-small-en-v1.5) | MIT; English embedding model | Default local FastEmbed embedding, tested at 384 dimensions |
| [Xenova/ms-marco-MiniLM-L-6-v2](https://huggingface.co/Xenova/ms-marco-MiniLM-L-6-v2) | ONNX conversion; converted model card did not expose an explicit license label when checked | Default FastEmbed cross-encoder, inference tested. Review the upstream model and converted repository terms for the intended distribution |
| [Groq supported models](https://console.groq.com/docs/models) | Hosted model IDs and availability are provider-managed | Configurable primary `openai/gpt-oss-20b`, fallback `llama-3.1-8b-instant`; recheck account access when deploying |

The Chronos cards did not list a generic Hugging Face Inference Provider deployment
when checked. This project uses local inference rather than assuming a free hosted
forecasting API. Separate AWS deployment options described by Amazon are outside
this package; no cloud resources or paid endpoints are provisioned.

The chronological baseline benchmark is the default because it provides measured,
store-specific validation at modest computational cost. Compare any neural candidate
on the same cutoffs, horizons and SKUs, recording MAE/WAPE, bias, latency, memory and
interval coverage. A smaller model may be preferable when its operational cost is
lower and accuracy is similar. No neural advantage has been measured for the user's
store because no actual store dataset was provided.

Other primary implementation references:

- [Streamlit documentation](https://docs.streamlit.io/)
- [CrewAI Flows](https://docs.crewai.com/en/concepts/flows)
- [FastEmbed repository and supported models](https://github.com/qdrant/fastembed)
- [FAISS](https://github.com/facebookresearch/faiss)
- [DDGS](https://github.com/deedy5/ddgs)
- [Prophet](https://facebook.github.io/prophet/)
- [SQLAlchemy](https://docs.sqlalchemy.org/)
- [Alembic](https://alembic.sqlalchemy.org/)

Python dependencies retain their own licenses and notices. Optional OCR uses
PyMuPDF; check its distribution terms independently of the embedding model's license.
An installed-version list is provided; it is not a complete license or dependency audit.

// bev-decide -- bev-decider-0.4B on llama.cpp, served over HTTP.
//
//   bev-decide -m bev-decider-backbone-Q8_0.gguf --head bev_head.json \
//              [--device HTP0 -ngl 99 | --device none] [-t 6] [-c 4096] \
//              [--host 127.0.0.1] [--port 8082] [--max-options 16]
//
//   POST /v1/systemone   {"state": str, "questions": {id: {type, instructions, criteria}}[, "debug": true]}
//                        -> {"model", "answers": {id: answer}, "latency_ms", "usage", "timings"
//                            [, "token_ids": {id: {prompt, options, answer}}]}
//                        answer as bev_decider: choice {type, choice, probabilities},
//                        noul {type, noul}, score {type, score, probabilities}
//   GET  /health         {"status": "ok"}
//   GET  /v1/models
//
// The transformer is the GGUF (bench/bev_convert.py + convert_hf_to_gguf.py);
// the decision head is bev_head.bin, run in fp32/double on the CPU
// (bev_core.hpp). One request at a time: the lane runs one call in flight.
//
// Per question, three llama_decode calls (bev_core.hpp explains the layout):
//   1. the prompt, sequence 0
//   2. every option at once, option i in sequence i+1, positions from P,
//      after copying sequence 0's cells to each option sequence
//   3. the answer phrase in sequence N+1, after copying the prompt's and every
//      option's cells to it
// Embeddings (pooling none = the final-norm hidden state, Qwen3Model's
// last_hidden_state) are read at each option's last content token and at the
// last answer token. Memory is cleared between questions.
//
// Requests: state, instructions and criteria must be strings (bev_decider also
// accepts JSON values, rendered with Python's json.dumps; not reproduced here).
//
// Built against the SAME llama.cpp commit as the board's llama-server
// (b11371, 99b95488): device/bev_decide/build_android.sh.

#include "bev_core.hpp"

#include "ggml-backend.h"
#include "llama.h"
#include "nlohmann/json.hpp"

#include <arpa/inet.h>
#include <netinet/in.h>
#include <signal.h>
#include <sys/socket.h>
#include <unistd.h>

#include <chrono>
#include <cstring>
#include <fstream>
#include <iostream>
#include <memory>
#include <sstream>

using json = nlohmann::ordered_json;   // keep criteria in request order, as Python dicts do

namespace {

struct Args {
    std::string model, head, host = "127.0.0.1", device = "HTP0";
    int port = 8082, ngl = 99, threads = 6, n_ctx = 4096, max_options = 16;
};

[[noreturn]] void usage(const char * why) {
    std::cerr << "bev-decide: " << why << "\n"
              << "usage: bev-decide -m <gguf> --head <bev_head.json> [--device HTP0|none] [-ngl N]\n"
              << "                  [-t threads] [-c n_ctx] [--host H] [--port P] [--max-options N]\n";
    std::exit(2);
}

Args parse(int argc, char ** argv) {
    Args a;
    for (int i = 1; i < argc; ++i) {
        std::string k = argv[i];
        auto val = [&]() -> std::string {
            if (i + 1 >= argc) usage(("missing value for " + k).c_str());
            return argv[++i];
        };
        if (k == "-m") a.model = val();
        else if (k == "--head") a.head = val();
        else if (k == "--device") a.device = val();
        else if (k == "-ngl") a.ngl = std::stoi(val());
        else if (k == "-t") a.threads = std::stoi(val());
        else if (k == "-c") a.n_ctx = std::stoi(val());
        else if (k == "--host") a.host = val();
        else if (k == "--port") a.port = std::stoi(val());
        else if (k == "--max-options") a.max_options = std::stoi(val());
        else usage(("unknown argument " + k).c_str());
    }
    if (a.model.empty() || a.head.empty()) usage("-m and --head are required");
    return a;
}

double ms_since(std::chrono::steady_clock::time_point t0) {
    return std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - t0).count();
}

class BadRequest : public std::runtime_error {
    using std::runtime_error::runtime_error;
};

// bev_head.json + bev_head.bin (bench/bev_convert.py) -> the head and the encoding constants.
void load_head(const std::string & path, bev::Head & head_, bev::EncodingConsts & consts_) {
    std::ifstream f(path);
    if (!f) throw std::runtime_error("cannot read " + path);
    json m = json::parse(f);
    if (m.at("dtype") != "F32" || m.at("byteorder") != "little")
        throw std::runtime_error("bev_head.json: expected F32 little-endian");
    std::string bin_path = path.substr(0, path.find_last_of('/') + 1) + "bev_head.bin";
    std::ifstream bf(bin_path, std::ios::binary);
    if (!bf) throw std::runtime_error("cannot read " + bin_path);
    std::vector<char> raw((std::istreambuf_iterator<char>(bf)), std::istreambuf_iterator<char>());
    std::vector<float> bin(raw.size() / 4);
    std::memcpy(bin.data(), raw.data(), bin.size() * 4);
    std::vector<bev::TensorSpec> specs;
    for (auto it = m.at("tensors").begin(); it != m.at("tensors").end(); ++it) {
        bev::TensorSpec s;
        s.name = it.key();
        s.shape = it.value().at("shape").get<std::vector<int64_t>>();
        s.offset = it.value().at("offset").get<int64_t>();
        s.nbytes = it.value().at("nbytes").get<int64_t>();
        specs.push_back(s);
    }
    head_.load(bin, specs, m.at("hidden_dim").get<int>(), m.at("new_dim").get<int>(),
               m.at("num_layers").get<int>(), m.at("num_task_types").get<int>(),
               m.at("layer_norm_eps").get<double>());
    if (m.at("gelu") != "erf") throw std::runtime_error("bev_head.json: only the erf GELU is implemented");
    for (auto it = m.at("task_prompts").begin(); it != m.at("task_prompts").end(); ++it)
        consts_.task_prompts[it.key()] = it.value().get<std::string>();
    for (auto it = m.at("task_types").begin(); it != m.at("task_types").end(); ++it)
        consts_.task_types[it.key()] = it.value().get<int>();
    consts_.answer_prompt = m.at("answer_prompt").get<std::string>();
    consts_.option_begin = m.at("option_begin").get<std::string>();
    consts_.option_end = m.at("option_end").get<std::string>();
    consts_.max_state_tokens = m.at("max_state_tokens").get<int>();
    consts_.max_choice_tokens = m.at("max_choice_tokens").get<int>();
}


// ---------------------------------------------------------------------------
class Decider {
  public:
    Decider(const Args & a) : args_(a) {
        load_head(a.head, head_, consts_);
        llama_backend_init();
        ggml_backend_load_all();            // as llama-server (common_init) does

        llama_model_params mp = llama_model_default_params();
        if (a.device == "none") {
            devs_ = {nullptr};
            mp.n_gpu_layers = 0;
        } else {
            ggml_backend_dev_t d = ggml_backend_dev_by_name(a.device.c_str());
            if (d == nullptr) throw std::runtime_error("no device named " + a.device);
            devs_ = {d, nullptr};
            mp.n_gpu_layers = a.ngl;
        }
        mp.devices = devs_.data();
        model_ = llama_model_load_from_file(a.model.c_str(), mp);
        if (model_ == nullptr) throw std::runtime_error("cannot load " + a.model);
        vocab_ = llama_model_get_vocab(model_);
        if (llama_model_n_embd(model_) != head_.H)
            throw std::runtime_error("model hidden size " + std::to_string(llama_model_n_embd(model_)) +
                                     " != head hidden_dim " + std::to_string(head_.H));

        llama_context_params cp = llama_context_default_params();
        cp.n_ctx = (uint32_t) a.n_ctx;
        cp.n_batch = (uint32_t) a.n_ctx;            // the prompt goes in one decode
        cp.n_seq_max = (uint32_t) (a.max_options + 2);
        cp.n_threads = cp.n_threads_batch = a.threads;
        cp.embeddings = true;
        cp.pooling_type = LLAMA_POOLING_TYPE_NONE;  // per-token hidden states
        cp.kv_unified = true;                       // sequences share the prompt's cells
        ctx_ = llama_init_from_model(model_, cp);
        if (ctx_ == nullptr) throw std::runtime_error("cannot create the context");
        mem_ = llama_get_memory(ctx_);
        std::cerr << "bev-decide: model " << a.model << ", device " << a.device << ", ngl " << mp.n_gpu_layers
                  << ", n_ctx " << a.n_ctx << ", n_seq_max " << cp.n_seq_max << ", hidden " << head_.H << "\n";
    }

    ~Decider() {
        if (ctx_) llama_free(ctx_);
        if (model_) llama_model_free(model_);
        llama_backend_free();
    }

    json models() const {
        return {{"models", json::array({json{{"name", "bev-decider-0.4b"}, {"source", args_.model},
                                             {"device", args_.device}, {"max_state_tokens", consts_.max_state_tokens}}})}};
    }

    json systemone(const json & req) {
        auto t0 = std::chrono::steady_clock::now();
        if (!req.is_object() || !req.contains("questions") || !req["questions"].is_object() ||
            req["questions"].empty())
            throw BadRequest("questions is empty");
        if (!req.contains("state") || !req["state"].is_string())
            throw BadRequest("state must be a string (JSON states are not supported by bev-decide)");
        const std::string state = req["state"].get<std::string>();
        json answers = json::object();
        // "debug": true -> the token ids of every question (conformance:
        // bench/bev_conformance.py compares them with bev_decider's encoder)
        const bool debug = req.value("debug", false);
        json token_ids = json::object();
        int64_t tokens = 0;
        double t_tok = 0, t_dec = 0, t_head = 0;
        for (auto it = req["questions"].begin(); it != req["questions"].end(); ++it) {
            bev::Question q = question(it.key(), it.value());
            auto t1 = std::chrono::steady_clock::now();
            bev::Layout L;
            try {
                L = bev::encode(state, q, consts_, tok_fn(), detok_fn());
            } catch (const std::invalid_argument & e) {
                throw BadRequest(std::string("invalid question ") + it.key() + ": " + e.what());
            }
            t_tok += ms_since(t1);
            if ((int) L.options.size() > args_.max_options)
                throw BadRequest("too many options (" + std::to_string(L.options.size()) + " > --max-options " +
                                 std::to_string(args_.max_options) + ")");
            if (L.n_tokens() > args_.n_ctx)
                throw BadRequest("question needs " + std::to_string(L.n_tokens()) + " tokens > n_ctx " +
                                 std::to_string(args_.n_ctx));
            auto t2 = std::chrono::steady_clock::now();
            std::vector<std::vector<float>> choice_emb;
            std::vector<float> answer_emb;
            run(L, choice_emb, answer_emb);
            t_dec += ms_since(t2);
            auto t3 = std::chrono::steady_clock::now();
            std::vector<double> p = head_.forward(choice_emb, answer_emb, L.task_type);
            t_head += ms_since(t3);
            tokens += L.n_tokens();
            answers[it.key()] = answer(q.type, L.keys, p);
            if (debug) token_ids[it.key()] = {{"prompt", L.prompt}, {"options", L.options}, {"answer", L.answer}};
        }
        json out = {{"model", req.value("model", std::string("bev-decider-0.4b"))},
                    {"answers", answers},
                    {"latency_ms", std::round(ms_since(t0) * 10) / 10},
                    {"usage", {{"prompt_tokens", tokens}}},
                    {"timings", {{"tokenize_ms", t_tok}, {"decode_ms", t_dec}, {"head_ms", t_head}}}};
        if (debug) out["token_ids"] = token_ids;
        return out;
    }

  private:
    Args args_;
    bev::Head head_;
    bev::EncodingConsts consts_;
    std::vector<ggml_backend_dev_t> devs_;
    llama_model * model_ = nullptr;
    const llama_vocab * vocab_ = nullptr;
    llama_context * ctx_ = nullptr;
    llama_memory_t mem_ = nullptr;

    static bev::Question question(const std::string & id, const json & j) {
        bev::Question q;
        if (!j.is_object() || !j.contains("type") || !j["type"].is_string())
            throw BadRequest("question " + id + ": type missing");
        q.type = j["type"].get<std::string>();
        if (!j.contains("instructions") || !j["instructions"].is_string())
            throw BadRequest("question " + id + ": instructions must be a string");
        q.instructions = j["instructions"].get<std::string>();
        if (j.contains("criteria") && !j["criteria"].is_null()) {
            const json & c = j["criteria"];
            if (c.is_object()) {
                for (auto it = c.begin(); it != c.end(); ++it) {
                    if (!it.value().is_string() && !it.value().is_null())
                        throw BadRequest("question " + id + ": criteria values must be strings");
                    q.criteria.emplace_back(it.key(), it.value().is_null() ? "" : it.value().get<std::string>());
                }
            } else if (c.is_array()) {
                for (size_t i = 0; i < c.size(); ++i) {
                    if (!c[i].is_string()) throw BadRequest("question " + id + ": score levels must be strings");
                    q.criteria.emplace_back(std::to_string(i), c[i].get<std::string>());
                }
            } else {
                throw BadRequest("question " + id + ": criteria must be an object or a list");
            }
        }
        return q;
    }

    static json answer(const std::string & type, const std::vector<std::string> & keys,
                       const std::vector<double> & p) {
        if (type == "noul") return {{"type", "noul"}, {"noul", p[1]}};
        json probs = json::object();
        for (size_t i = 0; i < keys.size(); ++i) probs[keys[i]] = p[i];
        if (type == "choice") {
            size_t best = 0;                     // first maximum, as Python's max over range
            for (size_t i = 1; i < p.size(); ++i)
                if (p[i] > p[best]) best = i;
            return {{"type", "choice"}, {"choice", keys[best]}, {"probabilities", probs}};
        }
        double e = 0;
        for (size_t i = 0; i < p.size(); ++i) e += (double) i * p[i];
        return {{"type", "score"}, {"score", e}, {"probabilities", probs}};
    }

    // HF Qwen2Tokenizer.encode(text): no BOS (add_bos_token false), added
    // tokens in the text matched (split_special_tokens false) -> parse_special.
    bev::Tokenize tok_fn() const {
        return [this](const std::string & s) {
            int32_t n = -llama_tokenize(vocab_, s.data(), (int32_t) s.size(), nullptr, 0, false, true);
            bev::Tokens t((size_t) std::max(n, 0));
            if (n > 0 && llama_tokenize(vocab_, s.data(), (int32_t) s.size(), t.data(), n, false, true) != n)
                throw std::runtime_error("tokenize failed");
            return t;
        };
    }

    // HF decode(skip_special_tokens=False, clean_up_tokenization_spaces=False)
    bev::Detokenize detok_fn() const {
        return [this](const bev::Tokens & t) {
            int32_t n = llama_detokenize(vocab_, t.data(), (int32_t) t.size(), nullptr, 0, false, true);
            std::string s((size_t) std::max(-n, 0), '\0');
            if (n < 0 && llama_detokenize(vocab_, t.data(), (int32_t) t.size(), &s[0], -n, false, true) != -n)
                throw std::runtime_error("detokenize failed");
            return s;
        };
    }

    void decode(llama_batch & b, const char * what) {
        int32_t rc = llama_decode(ctx_, b);
        if (rc != 0) throw std::runtime_error(std::string("llama_decode (") + what + ") returned " + std::to_string(rc));
    }

    std::vector<float> emb(int32_t i) {
        const float * e = llama_get_embeddings_ith(ctx_, i);
        if (e == nullptr) throw std::runtime_error("no embedding for batch index " + std::to_string(i));
        return std::vector<float>(e, e + head_.H);
    }

    void run(const bev::Layout & L, std::vector<std::vector<float>> & choice_emb, std::vector<float> & answer_emb) {
        const int P = L.P(), N = (int) L.options.size(), A = N + 1;
        llama_memory_clear(mem_, true);
        llama_batch b = llama_batch_init(std::max(L.n_tokens(), 1), 0, 1);
        auto add = [&](int32_t id, llama_pos pos, llama_seq_id seq, bool out) {
            int i = b.n_tokens++;
            b.token[i] = id;
            b.pos[i] = pos;
            b.n_seq_id[i] = 1;
            b.seq_id[i][0] = seq;
            b.logits[i] = out;
        };
        try {
            // 1. prompt, seq 0 (its last token is output only so the batch has one)
            b.n_tokens = 0;
            for (int k = 0; k < P; ++k) add(L.prompt[k], k, 0, k == P - 1);
            decode(b, "prompt");
            for (int s = 1; s <= N; ++s) llama_memory_seq_cp(mem_, 0, s, -1, -1);

            // 2. options, option i in seq i+1 from position P; output at the read token
            b.n_tokens = 0;
            std::vector<int32_t> read_at(N);
            for (int i = 0; i < N; ++i) {
                const bev::Tokens & o = L.options[i];
                for (int k = 0; k < (int) o.size(); ++k) {
                    if (k == L.read_idx[i]) read_at[i] = b.n_tokens;
                    add(o[k], P + k, i + 1, k == L.read_idx[i]);
                }
            }
            decode(b, "options");
            choice_emb.clear();
            for (int i = 0; i < N; ++i) choice_emb.push_back(emb(read_at[i]));

            // 3. answer, seq N+1, which sees the prompt and every option
            llama_memory_seq_cp(mem_, 0, A, -1, -1);
            for (int s = 1; s <= N; ++s) llama_memory_seq_cp(mem_, s, A, P, -1);
            b.n_tokens = 0;
            const int a0 = L.answer_pos0(), na = (int) L.answer.size();
            for (int k = 0; k < na; ++k) add(L.answer[k], a0 + k, A, k == na - 1);
            decode(b, "answer");
            answer_emb = emb(na - 1);
        } catch (...) {
            llama_batch_free(b);
            throw;
        }
        llama_batch_free(b);
    }
};

// ---------------------------------------------------------------------------
// Minimal HTTP/1.1: one connection at a time, Content-Length bodies,
// Connection: close. Enough for the stdlib client in llm_backend.py.
bool read_request(int fd, std::string & method, std::string & path, std::string & body) {
    std::string buf;
    char tmp[65536];
    size_t hdr_end;
    while ((hdr_end = buf.find("\r\n\r\n")) == std::string::npos) {
        ssize_t n = recv(fd, tmp, sizeof(tmp), 0);
        if (n <= 0 || buf.size() > (1 << 16)) return false;
        buf.append(tmp, (size_t) n);
    }
    std::istringstream hs(buf.substr(0, hdr_end));
    std::string line;
    std::getline(hs, line);
    std::istringstream rl(line);
    rl >> method >> path;
    size_t len = 0;
    while (std::getline(hs, line)) {
        std::string low = line;
        for (auto & ch : low) ch = (char) std::tolower((unsigned char) ch);
        if (low.rfind("content-length:", 0) == 0) len = std::stoul(line.substr(15));
    }
    if (len > (16u << 20)) return false;
    body = buf.substr(hdr_end + 4);
    while (body.size() < len) {
        ssize_t n = recv(fd, tmp, sizeof(tmp), 0);
        if (n <= 0) return false;
        body.append(tmp, (size_t) n);
    }
    body.resize(len);
    return true;
}

void respond(int fd, int code, const json & j) {
    std::string body = j.dump();
    const char * reason = code == 200 ? "OK" : code == 400 ? "Bad Request" : code == 404 ? "Not Found"
                                                                                        : "Internal Server Error";
    std::string head = "HTTP/1.1 " + std::to_string(code) + " " + reason +
                       "\r\nContent-Type: application/json\r\nContent-Length: " + std::to_string(body.size()) +
                       "\r\nConnection: close\r\n\r\n";
    std::string all = head + body;
    size_t off = 0;
    while (off < all.size()) {
        ssize_t n = send(fd, all.data() + off, all.size() - off, 0);
        if (n <= 0) return;
        off += (size_t) n;
    }
}

}  // namespace

int main(int argc, char ** argv) {
    Args a = parse(argc, argv);
    signal(SIGPIPE, SIG_IGN);
    std::unique_ptr<Decider> dec;
    try {
        dec.reset(new Decider(a));
    } catch (const std::exception & e) {
        std::cerr << "bev-decide: " << e.what() << "\n";
        return 1;
    }
    int srv = socket(AF_INET, SOCK_STREAM, 0);
    int on = 1;
    setsockopt(srv, SOL_SOCKET, SO_REUSEADDR, &on, sizeof(on));
    sockaddr_in addr{};
    addr.sin_family = AF_INET;
    addr.sin_port = htons((uint16_t) a.port);
    if (inet_pton(AF_INET, a.host.c_str(), &addr.sin_addr) != 1 ||
        bind(srv, (sockaddr *) &addr, sizeof(addr)) != 0 || listen(srv, 8) != 0) {
        std::cerr << "bev-decide: cannot listen on " << a.host << ":" << a.port << "\n";
        return 1;
    }
    std::cerr << "bev-decide: listening on " << a.host << ":" << a.port << "\n";
    for (;;) {
        int fd = accept(srv, nullptr, nullptr);
        if (fd < 0) continue;
        std::string method, path, body;
        if (!read_request(fd, method, path, body)) {
            close(fd);
            continue;
        }
        try {
            if (method == "GET" && path == "/health") respond(fd, 200, {{"status", "ok"}});
            else if (method == "GET" && path == "/v1/models") respond(fd, 200, dec->models());
            else if (method == "POST" && path == "/v1/systemone") respond(fd, 200, dec->systemone(json::parse(body)));
            else respond(fd, 404, {{"error", "no route " + method + " " + path}});
        } catch (const BadRequest & e) {
            respond(fd, 400, {{"error", e.what()}});
        } catch (const json::exception & e) {
            respond(fd, 400, {{"error", std::string("bad JSON: ") + e.what()}});
        } catch (const std::exception & e) {
            std::cerr << "bev-decide: " << e.what() << "\n";
            respond(fd, 500, {{"error", e.what()}});
        }
        close(fd);
    }
}

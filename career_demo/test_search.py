from data_loader import load_job_data, search_jobs, get_job_detail

FILE_PATH = "career_jobs.xlsx"

df = load_job_data(FILE_PATH)

print("총 직업 수:", len(df))

query = "행정학"
results = search_jobs(df, query)

print(f"\n[검색어: {query}]")
print(results[["job", "score"]].head(10))

detail = get_job_detail(df, "행정학연구원")
if detail:
    print("\n[행정학연구원 상세]")
    print("job:", detail["job"])
    print("summary:", detail["summary"])
    print("empway:", detail["empway"])
    print("prepareway:", detail["prepareway"])
    print("job_possibility:", detail["job_possibility"])
    print("contact_list:", detail["contact_list"])
    print("major_list(상위 5개):", detail["major_list"][:5])
else:
    print("직업을 찾지 못했습니다.")